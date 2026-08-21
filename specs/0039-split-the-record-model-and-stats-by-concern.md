# 0039: Split the record model and the stats module by concern

- **Status:** Not started
- **Kind:** feature (cleanup)
- **Effort:** S
- **Origin:** code structure review of `src/gcmon`, 2026-08-15
- **Respects:** [ADR-0009](../docs/adr/0009-nanoseconds-canonical-time-unit.md) (names the
  module holding the ns→µs conversion; **amended, not contradicted**),
  [ADR-0015](../docs/adr/0015-gc-loss-spans-on-their-own-track.md) (names the modules holding
  the loss record and the gap accounting; likewise),
  [ADR-0016](../docs/adr/0016-the-ring-is-the-statistics-unit.md) (names the module that keys
  everything on the ring; likewise)

## 1. Problem statement

Two modules have accumulated three jobs each, and the cost shows up as import fan-out.
`model/data.py` holds the record structs, the JSONL decoder, the unit conversions and the
Perfetto arg text, so the JSON encoder imports it to get `ts_to_us`, the control server imports
it to build an instant message, and `stats` imports it to convert seconds to nanoseconds. Three
modules with nothing in common depend on one module for three unrelated reasons, and each of
them drags the whole record model in behind it.

The fan-out has widened since the review. `secs_to_ns` has five callers in four layers now: the
CLI validates `--rate` and `GCMON_RATE` through it in two places, the poll loop sizes a tick
with it, the loss accumulator spans an interval with it, and the streaming statistics convert a
lifetime with it. `dur_to_ms` has two, one of them the pyperf metrics, whose only reason to know
`model` exists is that multiplication. Arithmetic on two numbers is what most of the layers
above `model` came to it for.

`stats/stats.py` is the same shape at larger scale: 749 lines holding a percentile accumulator
that has nothing to do with GC, nine metric adapters that are a name and a two-field getter
apiece, and the streaming aggregation with its loss, ring and lifetime bookkeeping. 0041 gave
`stats` a directory, which moved the file without splitting it. The test package already knows
where the seam runs: `tests/stats/` is split into `test_stats.py`, `test_metrics.py`,
`test_streaming_stats.py` and `test_stats_output.py`, four files along a line the source does
not have.

Nothing an operator sees is wrong. The cost is that every one of these modules is on the import
path of things that need a tenth of it, and a reader looking for the percentile logic opens a
file that starts with GC field guards.

## 2. Solution

No behaviour changes at all; this is a move. What changes is that a module's name predicts its
contents, an importer takes on the dependency it actually wants, and the source layout matches
the test layout that already exists.

## 3. User stories

1. As a maintainer looking for the percentile accumulator, I want it in a file named for it, so
   that I do not read past two hundred lines of GC field handling to reach it.
2. As a maintainer of the JSON encoder or of the CLI's option readers, I want to import a unit
   conversion without pulling in the record model, so that the dependency graph says what the
   code actually needs.
3. As a maintainer of the control plane, I want to build an instant message without importing
   the statistics vocabulary, so that a change to the record model does not touch the control
   server's imports.
4. As a maintainer adding a test, I want the source file layout to match `tests/stats/`, so
   that I know which file a new test belongs beside.
5. As someone reading gcmon for the first time, I want the record model in one place and the
   presentation strings somewhere else, so that "what is a record" is answerable without
   reading the Perfetto arg formatting.
6. As a maintainer, I want the ADRs that anchor on these module paths updated in the same
   change, so that a record does not point at a file that no longer exists.

## 4. Implementation decisions

**4.1: `model/data.py` splits three ways.**

| New home | Contents | Imported by |
|---|---|---|
| the record model, keeping `model/data.py` | `GCStatsInfo`, `InstantMsg`, `GenLoss`, `LossMsg`, `from_mapping`, `instant_msg` | monitor, loss, control server, the JSONL reader |
| the unit conversions, in `support/` | `ts_to_us`, `dur_to_ms`, `secs_to_ns` | the JSON encoder, both CLI option readers, the poll loop, loss, the streaming statistics, stats output, the pyperf metrics |
| the slice text, beside `trace_converter` | `duration_text`, `seen_text`, `lost_collections` | `trace_converter`, and only `trace_converter` |

**The conversions land in `support/`, not `model/`.** They divide and multiply two numbers and
name no record type, and eight callers in five layers want them. 0041 put `support` at the
bottom for this: its row in `ALLOWED` imports nothing and every other layer may import it, so
the move adds no edge to the table. Leaving them in `model/` keeps the CLI and the pyperf
metrics importing the record model's layer to convert seconds; after the move
`pyperf/metrics.py` does not import `model` at all.

The slice text is presentation for a `GC Loss` slice's args and has exactly one caller. It goes
beside that caller rather than into a module of its own; `duration_text`'s docstring already
describes itself as "the way the Perfetto UI writes a duration", which is a statement about the
consumer, not about gcmon's data.

**4.2: `stats/stats.py` splits three ways**, matching `tests/stats/`: the accumulator (`Stats`,
`get_quantile_value`, the DDSketch fallback), the metric table (`Metric`, the nine adapters,
`METRICS`), and the streaming aggregation (`StreamingStats`, `RingStats`, `LossTotals`,
`PauseTotals`, `CumulativeCounters`, `_record` and the `RingKey` and `EpochedRing` aliases).
`stats_output` stays where it is: it is presentation, it already has one job, and 0041 put it in
this directory already.

**4.3: The metric table is whatever [0035](0035-derive-every-gc-sub-phase-from-one-table.md)
leaves.** If 0035 has landed, this module is the derivation from the phase table and is a few
lines; if it has not, it is the nine `Metric` classes moved verbatim. Either way this spec does
not change what a metric is, and **nothing forces the order**. Taking this one first moves nine
classes that 0035 then deletes, which costs the move and no decisions, and it hands 0035 a
module named for the table rather than a stretch of a 749-line file.

**4.4: The public surface is `gcmon.__all__`, and it does not move.** Every name in it keeps
working from `gcmon` directly, `__version__` included, which the package resolves on first use.
No shim keeps the old deep paths alive: 0041 moved nineteen modules and re-exported none of
them, for the reason that holds here too, that no document outside the source names one. If this
lands in the release 0041 is in, the CHANGELOG line 0041 wrote covers it; once that release has
shipped, this needs a breaking-changes line of its own.

**4.5: Five implementation notes across three ADRs are amended in the same change.** ADR-0009
names the module holding the ns→µs conversion, ADR-0015 the one that records every gap, and
ADR-0016 names `gcmon.stats.stats` three times, twice in the decision itself and once in the
implementation notes. ADR-0015's other note, that `model/data.py` holds the loss record, stays
true, because the record model keeps the file it is in. The ADR README's rule is explicit: amend
a record when a name it anchors on moves. Each of the five is a rename inside a record, not a
change of decision.

**Rejected: leave the record model alone and only split `stats`.** The unit conversions are the
reason the JSON encoder, the CLI and the pyperf metrics import the record model, and they are
three functions. Splitting the larger module while leaving the smaller cross-layer dependency in
place gets the less useful half.

**Rejected: one module per struct.** `GenLoss` and `LossMsg` are one record type in two pieces
and are read together everywhere; separating them would be layout for its own sake.

## 5. Seams and testing decisions

- **Seam:** the existing suite, unchanged except for imports. There is no behaviour here to
  observe, so the highest available seam is "every test that passed still passes, with no test
  body edited". A test body that has to change is evidence something moved that should not have.
- **New seam needed:** none, and none is wanted. Do not add tests asserting that a module
  exports a given name; that pins the layout this spec is choosing, and the next reorganization
  would have to delete them. `tests/architecture/test_layering.py` already fails a piece that
  lands in the wrong layer, and it needs no new entry here: only `monitoring` and `cli` import
  `support` today, and the three directions this adds, from `model`, `exporters` and `stats`,
  are in `ALLOWED` already.
- **What makes a good test here:** nothing new. The value is in what is *not* required: if this
  move needs a new test, it was not a move. The one thing worth checking mechanically is that
  the public surface is unchanged: `gcmon.__all__` still resolves, every name in it importable
  from `gcmon` directly.
- **Prior art:** the test package is already split both ways. `tests/stats/` is the four-way
  split this creates in the source, and `tests/test_time.py` holds the conversion tests that
  `tests/test_data.py` does not, which is the line 4.1 draws through the record model.
- **Cases:**
  1. The full suite passes with import lines updated and no test body changed.
  2. Every name in `gcmon.__all__` imports from `gcmon` directly, as it does today.
  3. Regression guard: `gcmon run` over a fixture produces byte-identical output on all five
     formats. A pure move that changes a byte has moved something else too.

## 6. Out of scope

- Re-keying `_running_rings`, the question 0046 left open. It is
  [0051](0051-key-the-running-rings-by-pid.md) now. Section 5 promises a move with no test body
  edited, and the re-key rewrites six assertions that read the flat shape, so carrying it here
  would blunt the one tripwire this spec has.
- Which layer each piece lands in, as a question of its own. That was 0041, which landed on
  2026-08-21 and is retired: `model/`, `stats/` and `support/` all exist, so 4.1 names a layer
  per piece instead of arguing for a shape.
- The phase table. [0035](0035-derive-every-gc-sub-phase-from-one-table.md) owns it, whichever
  of the two lands first.
- `exporters/chrome_trace_io.py`, which has the same grab-bag shape (JSONL read, JSONL write,
  Chrome parse, two normalizers, combine orchestration). Most of it is claimed by
  [0037](0037-one-meta-emission-path-for-live-and-combined-traces.md) and 0035; splitting what
  survives is worth doing then, with the remainder in view.
- Splitting `perfetto_format`, which [0030](0030-exporter-hygiene-batch.md) already named and
  deferred.
- Any change to the JSONL schema, the `--stats` table or the Perfetto arg strings. All three are
  public and this moves code, not output.

## 7. Further notes

0035 and this one can go in either order. Taking 0035 first saves moving nine `Metric` classes
it deletes; taking this first gives 0035 a module named for the table to edit, and costs the
citations of `stats.METRICS` in 0035's own spec, which this renames. 0051 comes after this one
either way, since it rewrites assertions against `StreamingStats` and this moves the module
holding it. 0041 going first cost these files one extra move, which is spent, and paid for it by
settling the layer each piece belongs to.
