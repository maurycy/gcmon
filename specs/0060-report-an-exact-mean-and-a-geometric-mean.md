# 0060: Report an exact mean and a geometric mean in the statistics table

- **Status:** Not started
- **Kind:** feature (enhancement)
- **Effort:** S
- **Origin:** design session 2026-08-23 on comparing two tracefiles; the
  statistic `compare` needs (spec 0063) turned out to be missing from the
  table it would be comparing
- **Respects:**
  [ADR-0015](../docs/adr/0015-gc-loss-spans-on-their-own-track.md) (a scale
  factor corrects a sum and never a quantile),
  [ADR-0016](../docs/adr/0016-the-ring-is-the-statistics-unit.md) (the ring is
  the unit statistics are reported for),
  [ADR-0018](../docs/adr/0018-stats-requires-a-view-and-keeps-no-bare-alias.md)
  (the view words come from one enum)

## 1. Problem statement

The `Avg` column reads high on any lossy run, and nothing beside it says by
how much. It is the sampled mean: the records gcmon read, divided by how many
it read. A long GC run delays the next one, so its record sits in the ring
slot longer and survives to a poll more often than a short one's, which is the
bias the percentiles carry and the footer already warns about.

The table holds the numbers that remove it. `PauseTotals` carries the exact
count and the exact pause total for every pause row, reconstructed from the
target's cumulative counters, and their ratio is a mean over every collection
in the observed span whether or not its record survived. Nothing prints it.

The second gap is the arithmetic mean itself. GC pause durations are strongly
right-skewed, and a handful of gen-2 collections pull `Avg` away from what a
typical pause costs. An operator reading `Avg 1.328` beside `P50 1.323` on one
row and `Avg 33.542` beside `P50 38.937` on another has no summary that
behaves the same way on both.

## 2. Solution

`Avg` becomes exact on every row that has an exact counterpart, so on a lossy
run it reports the mean over every collection rather than over the ones gcmon
happened to read. On a run that lost nothing it does not move.

A new `Geo` column reports the geometric mean of the pauses gcmon read. It is
the summary that survives the skew: doubling one pause in a hundred moves it a
little, where it moves `Avg` by a percent of the total.

Sub-phase rows keep the sampled mean, because CPython accumulates a cumulative
total for the whole pause only and no exact count exists to divide by. They
are marked the way their `Count` and `Sum` cells are already marked.

## 3. User stories

1. As an operator reading a table from a run that lost records, I want `Avg`
   to describe every collection rather than the ones that survived, so that I
   do not read a mean inflated by the bias the footer warns me about.
2. As an operator on a run that lost nothing, I want every number I already
   trusted to be unchanged, so that this costs me nothing.
3. As an operator comparing a gen-0 row against a gen-2 row, I want one
   central-tendency column that behaves the same way on both, so that I can
   read the shape without switching between `Avg` and `P50`.
4. As an operator reading a sub-phase row, I want to be able to tell that its
   mean is sampled while the pause row above it is exact, so that I do not
   compare two numbers computed over different intervals.
5. As someone trending `Avg` across a history that spans this change, I want
   to be told the numbers moved, so that I do not read a step in my chart as a
   regression.
6. As a maintainer, I want the geometric mean to cost constant memory, so that
   a long session does not pay for it the way the percentile buffer does.

## 4. Implementation decisions

**`Avg` reads `PauseTotals` where one exists.** `PauseTotals.exact_pause_ns`
over `PauseTotals.exact_count` is a mean over the observed span.
`stats_output` already holds the `PauseTotals` for each row, because `Cov` and
`F` come from it, so the cell changes and the plumbing does not. A row with no
`PauseTotals`, which is every sub-phase row and `Read Time`, keeps
`Stats.average()`.

**`Geo` accumulates as a running log sum, not from the buffer.** `Stats` gains
a sum of `log(value)` beside its existing sum and count, and the geometric
mean is `exp(logsum / count)`. That is constant memory and exact over every
value the instance saw, unlike the percentiles, which read a 1024-entry buffer
or a sketch. `materialize` then has nothing extra to settle.

`statistics.geometric_mean` is rejected for that reason: it takes a sequence,
so it would report the geometric mean of whatever the buffer still held rather
than of the run.

**Zero durations cannot reach it.** `streaming_stats._record` admits a value
only where the two timestamps differ, so no sample is zero and the logarithm
is always defined. That is the one constraint this change rests on which is
not local to it, and it belongs in a test rather than in a comment.

**The sub-phase marking follows the existing convention.** A sub-phase `Count`
and `Sum` already print their second number with a leading `~`, and only when
that row lost records. The sampled `Avg` takes the same mark under the same
condition, so a full-coverage run carries no marks anywhere and a lossy one
marks exactly the cells resting on an estimate.

**Rejected: a twelfth column.** Printing `Avg` and an exact mean side by side
leaves two adjacent cells whose difference nobody can read off the table, and
the sampled one has no remaining use once the exact one exists.

## 5. Seams and testing decisions

- **Seam:** `stats_output.print_stats`, through the existing table tests. It
  is the highest seam that observes the change, and both numbers are columns
  rather than trace content.
- **New seam needed:** none. `StreamingStats` is already driven directly by
  the statistics tests.
- **What makes a good test here:** feed a known record set and a known loss,
  then assert the printed `Avg` equals the exact mean computed by hand from
  the same figures. A test asserting only that `Avg` changed would pass on the
  wrong arithmetic.
- **Prior art:** the `Cov` and `F` column tests, which already build a
  `PauseTotals` carrying loss and assert a formatted cell.
- **Cases:**
  1. A lossy pause row prints the exact mean, and the same row's `Geo` is the
     geometric mean of the sampled durations alone.
  2. Regression guard: a run that lost nothing prints the table it printed
     before, `Avg` included, with `Geo` the only new column.
  3. A sub-phase row on a lossy run prints a marked, sampled `Avg`.
  4. A ring whose records all share one duration reports that duration as both
     `Avg` and `Geo`, which pins the log-sum arithmetic without a fixture.

## 6. Out of scope

- **Correcting the percentiles.** ADR-0015 settles that no scale factor fixes
  a quantile, and the geometric mean does not reopen it: it is computed from
  the sampled values and reads high for the same reason.
- **A geometric mean over exact values.** There is nothing to compute. A
  geometric mean needs the individual durations, and the durations of the runs
  gcmon missed are gone; only their total survives.
- **`Read Time`.** Monitor-side cost, with no generation and no `PauseTotals`,
  and its distribution is not skewed the way a pause distribution is.
- **The pyperf metadata keys.** `gc_pause_gen_N_*` are a published surface;
  adding to them is a separate decision carrying its own compatibility
  question.

## 7. Further notes

`Avg` moving is user-facing, so it needs a `CHANGELOG.md` entry under
`Breaking changes` and a note in `docs/statistics.md` shaped like the one
`docs/pyperf.md` already carries for `sum` and `count`: do not trend a history
that spans this change.

Spec 0063 depends on both columns. Nothing else does.
