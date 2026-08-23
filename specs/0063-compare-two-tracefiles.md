# 0063: Compare two tracefiles

- **Status:** Not started
- **Kind:** feature (enhancement)
- **Effort:** L
- **Origin:** design session 2026-08-23; pyperf's `compare_to` answers this
  question for benchmark timings and nothing answers it for GC
- **Respects:**
  [ADR-0015](../docs/adr/0015-gc-loss-spans-on-their-own-track.md) (a scale
  factor corrects a sum and never a quantile; the argument extends to the
  geometric mean),
  [ADR-0016](../docs/adr/0016-the-ring-is-the-statistics-unit.md),
  [ADR-0018](../docs/adr/0018-stats-requires-a-view-and-keeps-no-bare-alias.md)

## 1. Problem statement

Someone changing an allocator, a threshold or a library version wants one
question answered: did garbage collection get worse. They have two captures
and no way to ask.

What they can do today is print two statistics tables and read them side by
side. That works for one row and fails for sixty: the pids differ between the
runs so nothing lines up, the counts differ because the runs were not the same
length, and there is nothing to say whether a p99 that moved from 2.3 ms to
2.5 ms moved for a reason.

pyperf answers the same question for benchmark timings, and `compare_to` is
the shape people already know. Nothing in gcmon corresponds to it.

## 2. Solution

`gcmon compare <reference> <changed>...` prints one table, one row per
workload per generation, and says what changed.

Each row carries two verdicts, because "GC got worse" is two claims and they
can point in opposite directions. The **pause** verdict says whether
collections got longer or shorter, tested for significance. The **total**
verdict says whether the program spent more or less time collecting. A run
whose pauses got shorter while there were half again as many of them reads
`pause 1.11x shorter, total 1.24x more`, which is the true and useful
statement and the one a single verdict cannot make.

Rows that moved by less than `--min-change` read `no change`, and rows whose
movement did not clear the significance test read `not significant`. They are
different reasons and the table says which.

Two summary rows close the table. `Total` pools every record in the file, and
`Mean of Ratios` gives each workload one vote regardless of how many pauses it
produced.

`compare` reports. It exits zero unless the command itself failed.

## 3. User stories

1. As someone who changed a GC threshold, I want one table saying which
   benchmarks got worse, so that I do not read sixty pairs of tables.
2. As someone whose change made pauses shorter but more frequent, I want both
   facts, so that I do not ship a regression that looks like an improvement.
3. As someone comparing three builds, I want a column each against one
   reference, so that I can see a trend rather than run the command twice.
4. As someone whose two captures lost records at different rates, I want to be
   told, so that I do not read a sampling artefact as a regression.
5. As someone running a suite where one benchmark produces most of the pauses,
   I want a summary that does not let it decide the verdict alone.
6. As someone whose changed run stopped producing a benchmark, I want the
   unpaired row named, so that a suite that quietly ran less work does not
   read as an improvement.
7. As someone comparing a build against itself, I want every row to read
   unchanged, so that I can trust the threshold.
8. As someone piping this into a script, I want a stable exit status, so that
   a comparison never fails a build by reporting one.
9. As a maintainer, I want the comparison built from two tables produced by
   the existing code, so that `report` and `compare` cannot disagree.

## 4. Implementation decisions

**The comparison is two tables and a diff.** `compare` builds one table per
file through spec 0061's reader and spec 0062's workload level, and every
number it prints is a cell from one of them or a ratio of two. Nothing
computes statistics a second way.

**Rows pair by workload key, and generation.** The key comes from the
sanitizer, so it means the same thing in both files. A key present in one file
and not another is unpaired: it is printed, named as unpaired, and excluded
from `Mean of Ratios`.

The key set is itself checked. Two pyperformance runs pair correctly only if
both ran the same benchmarks in the same order, because the worker task number
is part of the key; a run against a filtered suite diverges after the first
missing benchmark. `compare` reports the divergence rather than pairing rows
that do not correspond.

**The headline is the geometric mean of pause durations, per generation.** It
is the summary that survives the skew of a pause distribution, and spec 0060
puts it in the table.

**It is a sampled statistic, and this is the risk the feature carries.** A
geometric mean can only be computed from individual durations, so it inherits
ADR-0015's problem whole: it reads high under loss, and `F` cannot correct it,
because `F` is a ratio of two totals and applying it to a mean of logs assumes
the lost pauses share a shape with the sampled ones. The failure this produces
is a reference at full coverage compared against a changed run at 20%, where
the changed geomean reads high from bias alone and the table reports a
regression that did not happen. The error is one-directional, so it does not
look like noise.

Three things answer it, and none of them is a correction:

- **Both files' `Cov` prints on every row.**
- **The row is flagged on coverage asymmetry, not on coverage level.** Where
  both runs lost a similar share, both geomeans are inflated by a similar
  factor and much of it cancels in the ratio. It is the difference between
  them that manufactures a verdict.
- **The exact mean prints beside the geomean.** Spec 0060 makes it exact over
  both terms, so it is the number to read when `Cov` says the geomean cannot
  be trusted.

**The test is Welch's t-test on the natural logs of the durations.** A
two-sample t-test on logs tests exactly whether two geometric means differ, so
the headline and the test are one computation. Welch rather than Student
because the two runs have different sample sizes and different variances as a
matter of course. `NormalDist` from the standard library supplies the CDF: at
the sample sizes a GC run produces the difference from a t distribution is
below the precision printed, and `math.lgamma` is there if a real one is ever
wanted. No numeric dependency is added.

**Consecutive GC pauses are not independent.** The heap grows through a run
and the pauses grow with it, so this is a time series and the test assumes it
is not. The p-value is therefore optimistic by an amount nothing in the file
can measure. This is stated in the documentation and not corrected: a
correction that cannot be validated would be worse than the caveat.

**`--min-change` is what keeps the test usable, so it is not optional.** At
several thousand pauses a row, a difference of a fraction of a percent clears
any significance threshold, and pyperf's default of 0% would flag every row. A
row is reported as changed only when it is both significant and past
`--min-change`.

The default is 5% and is provisional. What settles it is an A/A comparison:
capture one build twice, unchanged, and compare the two files. Every row must
read unchanged. That is written as a test, and the number that makes it pass
is the number that ships.

**`Count` and `Sum` cannot be tested, only thresholded.** They are one number
per file with no sample behind them, which is why the `total` verdict is
thresholded alone and says so.

**Two summary rows, because they answer different questions.** `Total` pools
every record, so a workload producing most of the pauses decides it.
`Mean of Ratios` is the unweighted geometric mean of the per-row ratios,
pyperf's row, where each workload counts once. It names how many rows it
folded, the way the lifetime-totals footer already names what it summed.

**An optional results file per trace supplies labels only.** `--results`
points at the harness's own output and turns `bm_base64#3` into
`ascii85_large`. Keys are correct without it, so it is never a precondition
for comparing, and the harness-version-specific tables it needs stay off the
path everyone uses.

**The exit status does not depend on the data.** A comparison that fails a
build by reporting a regression breaks every script that wanted the table, and
it would make the exit code depend on `--min-change`, whose default is
provisional. Unpaired rows and diverged key sets are reported in the table,
not in the status.

**Verdict wording.** `shorter` and `longer` for a pause, `more` and `less` for
a total. pyperf's `faster` and `slower` are rejected: faster could mean each
collection is quicker or that there are fewer of them, which are different
regressions with different causes and the two verdicts exist to separate them.

## 5. Seams and testing decisions

- **Seam:** the comparison takes two `StreamingStats` and returns rows. It is
  testable with two hand-built tables and no trace, no file and no subprocess,
  which is the highest seam available because everything below it is spec
  0061's and spec 0062's to test.
- **New seam needed:** the row-pairing and verdict layer. Nothing existing
  compares two tables.
- **What makes a good test here:** two tables built from known records, with
  the verdict asserted against arithmetic done by hand. For the statistics, a
  case where the answer is known independently: two identical distributions
  must not be significant, and a distribution against itself scaled by a
  constant must report exactly that ratio.
- **Prior art:** the statistics tests, which already build a `StreamingStats`
  directly; `tests/` for the CLI subcommands.
- **Cases:**
  1. A/A: one capture compared against a second capture of the same build
     reports every row unchanged. This is the acceptance test and it
     calibrates `--min-change`.
  2. A row whose pauses shortened while its count rose reports both verdicts,
     pointing opposite ways.
  3. A row significant at the test but under `--min-change` reads `no change`;
     one over `--min-change` but not significant reads `not significant`.
  4. Asymmetric coverage is flagged, and symmetric coverage at the same level
     is not.
  5. A workload in the reference and missing from the changed file is printed
     as unpaired and excluded from `Mean of Ratios`.
  6. Diverged key sets are reported rather than paired.
  7. Three files produce three columns against one reference.
  8. Every path exits zero: a regression, an unpaired row, a diverged key set.
     A missing file does not.

## 6. Out of scope

- **Failing a build.** No `--fail-on-regression`, for the reason in section 4.
  A caller wanting one reads the table.
- **Comparing captures that are not A/B.** `compare` assumes both files
  describe the same shape of run, which is what makes a pairing meaningful. It
  reports what it cannot pair and does not try to align two unrelated trees.
- **Correcting the geomean for loss.** There is nothing to correct it with.
- **A bootstrap confidence interval.** It would drop the normality assumption
  and not the independence one, which is the assumption actually violated, at
  the cost of thousands of resamples a row.
- **Comparing percentiles.** They are sampled and read high, and comparing two
  differently-biased quantiles is the mistake this spec spends section 4
  avoiding for the geomean.
- **Comparing `Read Time`.** It is not in a tracefile.
- **A results file that changes the pairing.** It supplies labels; a sidecar
  able to move rows would make two files pair differently depending on a
  third.

## 7. Further notes

Landing this earns an ADR: why the geometric mean, why a t-test on logs, why
the statistic is sampled and cannot be corrected by `F`, and why the two
verdicts are separate. It extends ADR-0015's argument to a new statistic
rather than restating it.

`compare` also takes `--table-format`, reusing `TableFormat`; `-b/--workload`,
repeatable, to filter rows; and `-G/--group-by-change`, sorting rows into
longer, shorter and unchanged.

**Reference** and **changed** are pyperf's words for the two sides and are
adopted; **Mean of Ratios** is new. Both belong in `CONTEXT.md` when this
lands, along with a line in the **Sampled** entry saying the geometric mean is
one.

Depends on specs 0060, 0061 and 0062.
