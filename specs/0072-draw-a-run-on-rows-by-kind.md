# 0072: Draw a run on rows by kind

- **Status:** Not started
- **Kind:** feature (enhancement)
- **Effort:** M
- **Origin:** design session 2026-10-03
- **Respects:**
  - [ADR-0007](../docs/adr/0007-shared-trace-converter-pipeline.md): the
    converter stays the one path from records to events and knows nothing of
    layouts. The layout is the encoder's.
  - [ADR-0024](../docs/adr/0024-an-event-names-the-track-it-is-drawn-on.md):
    an event names its track and the encoder derives every other row; the
    merged layout is a second derivation from the same tracks. Amended when
    this lands: a record's slices name a `PauseTrack` carrying the generation,
    which the process layout draws on the interpreter's one pause row; and the
    encoder emits a process descriptor ahead of a track's first packet in the
    process layout only.
  - [ADR-0011](../docs/adr/0011-process-lifetime-and-ordering.md): the
    `Processes` row is drawn the same in both layouts. Amended when this
    lands: the root descriptor and the process descriptors belong to the
    process layout. Both layouts rank processes.
  - [ADR-0010](../docs/adr/0010-process-identity-cmdline-and-start-marker.md):
    the process descriptor, its command line and its start stamp. Amended when
    this lands: process layout only; a merged trace carries the command line
    on the span.
  - [ADR-0028](../docs/adr/0028-draw-every-process-a-row-of-its-own.md): a row
    per process, its `Lifetime` slice and the counts on it. Amended when this
    lands: process layout only.
  - [ADR-0027](../docs/adr/0027-group-every-row-an-interpreter-owns.md): the
    interpreter groups. Amended when this lands: process layout only.
  - [ADR-0013](../docs/adr/0013-rss-sampling.md): RSS is Perfetto-only and
    sampled the same way. Amended when this lands: `rss` parents to the
    process row in the process layout, and sits in the `RSS` group in the
    merged one.
  - [ADR-0015](../docs/adr/0015-gc-loss-spans-on-their-own-track.md): one
    window per poll interval, the args and their emission order hold. Amended
    when this lands: the per-interpreter `GC Loss` row is the process
    layout's, and the rejected "one row for every interpreter" no longer holds
    for the merged one, where overlapping windows fold into lanes instead of
    nesting.
  - [ADR-0001](../docs/adr/0001-hand-rolled-perfetto-protobuf-encoder.md): the
    encoder already writes everything the merged layout needs: counter
    descriptors, `child_ordering` and `sibling_order_rank`.
  - [ADR-0021](../docs/adr/0021-write-one-trace-format.md): `--format` is
    unchanged, and the layout applies to `perfetto` alone. `combine` keeps
    writing the process layout.
  - [ADR-0014](../docs/adr/0014-perfetto-integration-test-strategy.md): the
    layout is asserted through the trace processor.

## 1. Problem statement

On a run over a process tree, the trace gives every process a row of its own,
and a process's pauses sit two groups down, under `Python Interpreters` and
`Interpreter {iid}`. A pyperformance run spawns thousands of processes.
Finding the one whose pauses you want means scrolling a list that long and
expanding two groups, and seeing when the tree collected, or where gcmon went
blind, means doing that for every process.

## 2. Solution

`--layout merged`, or `GCMON_LAYOUT=merged`, on `gcmon monitor` and
`gcmon run` writes the same run on these root rows:

```
All GC Pauses
  Gen0
  Gen1
  Gen2
GC Loss
Marks
Processes
RSS
  Process 38460
  Process 14012
  ...
```

Every pause in the run sits on its generation's row with its sub-phases inside
it, and every loss window on `GC Loss`. A row is as many lanes tall as the
most interpreters pausing, or blind, at once. A process's pauses are the ones
inside its span's window on `Processes`, and every pause and loss window
carries `pid` and `pid_epoch` to settle a window two processes share. `Marks`
holds the workload's marks, and `RSS` holds a counter per process.

The counter rows and the `Lifetime` slice's counts are gone: a counter's value
is an arg on its pause, and a `Lifetime` count is a count or a sum over the
process's pauses and loss windows. A reader who wants the `heap_size` chart or
a row per process records with the default, `--layout process`, which is
unchanged.

`--layout merged` with `--format jsonl` or `stdout` logs a warning and runs.

## 3. User stories

1. As someone reading a trace of a wide tree, I want every pause on a few
   rows, so that I can see when the run collected without opening a group per
   process.
2. As someone reading that trace, I want to find one process's pauses from its
   span, so that I do not scroll a row per process.
3. As someone reading it, I want each pause to say which process ran it, so
   that a window two processes share still tells them apart.
4. As someone reading it, I want gen-2 pauses on a row of their own, so that
   they stand out from the frequent gen-0 ones.
5. As someone reading it, I want every loss window on one row, so that I see
   where gcmon went blind across the run.
6. As an operator, I want the merged trace to keep every number the default
   one draws, so that choosing it costs a view and not data.
7. As a developer profiling one script under `gcmon run`, I want the default
   unchanged, so that I keep the counter charts and the row per process.
8. As an operator who asks for `--layout merged --format jsonl`, I want a
   warning, so that I know the layout did not apply.
9. As a CI job, I want `GCMON_LAYOUT` to stop the run on any value but
   `process` or `merged`, so that a typo does not write the other layout.
10. As a maintainer, I want both layouts checked against each other, so that a
    number one of them drops fails a test.

## 4. Implementation decisions

**The encoder takes the layout at construction.** `ProtobufEventEncoder` gains
a `layout` parameter, `PerfettoExporter` passes it through, and
`EventsExporterFactory` passes the option. The encoder calls three functions
today: `convert_trace_events_to_perfetto` per batch,
`emit_retired_process_row` per retired process and `finalize_perfetto_packets`
at close. A new module in `exporters` gives the merged layout the same three,
and the encoder picks one set at construction.

Rejected: a layout argument threaded through the `_emit_*` helpers in
`perfetto_format`. Every helper would carry a branch for a layout that draws
none of its rows.

**A record's slices go on a pause track.** `convert_item_to_trace_format`
places the pause and its sub-phases on a new `PauseTrack(process, iid, gen)`
instead of `InterpreterTrack(process, iid)`, and its counters stay on the
`InterpreterTrack`. Both layouts encode the same `TraceEvent`s, and the
converter still knows nothing of layouts (ADR-0007). A sub-phase has no
`generation` arg of its own, and its track now carries it. The process layout
keys its pause row on `(process, iid)`, so an interpreter's three generations
share one `GC Pauses` row and the trace stays byte-identical;
`get_interpreter_count` counts the distinct iids over a process's pause
tracks. The merged layout keys a `Gen{gen}` track on all three fields.

Rejected: recovering the generation in the encoder from the slice name, by
inverting the per-generation names in `model.names`. The converter has the
generation when it builds the slice, and the track is where an event says
which row it is drawn on (ADR-0024).

**Each track maps to a merged row:**

| An event on | Process layout | Merged layout |
|---|---|---|
| `PauseTrack`, a slice | `GC Pauses` in the interpreter group, one per `(process, iid)` | a track per `(process, iid, gen)` named `Gen{gen}`, parented to `All GC Pauses`, ranked by gen |
| `InterpreterTrack`, a counter | `heap_size`, or the `GC Metrics` group | not drawn |
| `LossTrack` | `GC Loss` in the interpreter group | a track per `(process, iid)` named `GC Loss` at the root |
| `ProcessTrack`, an instant | the process row | a track per process named `Marks` at the root |
| `ProcessTrack`, a counter | `rss` on the process row | a counter per process named for its span, parented to `RSS`, ranked by `get_process_track_rank` |
| a span | `Processes` | `Processes`, unchanged |

Both groups carry `child_ordering = EXPLICIT`. The trace processor merges
tracks sharing a name and a parent. It puts a slice into a free lane when the
slice's track has nothing open, and a slice that begins inside an open one
stays on that lane, so a sub-phase stays inside its pause; checked against the
pinned trace processor. A track per `(process, iid, gen)` is enough, since an
interpreter's collections serialize (ADR-0015).

**`pid` and `pid_epoch` go on pauses, loss windows and marks**, written by the
encoder from the event's `Process`, in the merged layout only. A sub-phase
gets neither, since it sits inside its pause. The process layout's row already
says whose a pause is, and the encoder's cost follows the annotation count, so
the default does not pay for them.

**Not drawn in the merged layout:** process descriptors, interpreter groups,
counters, the `Lifetime` slice and its counts, and the root descriptor. Every
counter value is an arg on the pause it came from, and every `Lifetime` count
is a count or a sum over the process's pauses and loss windows. The `RSS`
group is drawn because RSS values exist nowhere else. `_record_capture_totals`
does not run. `_record_process_lifetime` and `rank_processes` do, since a span
still needs its bounds and an `RSS` counter the rank its process row would
have in the process layout.

**Root rows sort by name**, with or without a root descriptor asking for
explicit ordering; checked against the pinned trace processor. `All GC Pauses`
is named to sort the pauses above `GC Loss`, the order the process layout
ranks them in inside an interpreter group (ADR-0027).

**Packets go out when the process layout's would.** A track's descriptor
precedes the first packet naming it. A span goes out at the flush that retires
its process or at close (ADR-0011), and a pause, a mark or a sample at its own
flush, so a killed run keeps what it would keep in the process layout.

**`PerfettoTrackState` gains the keys the merged layout allocates:** a pause
track per `(process, iid, gen)`, a marks track and an RSS counter per process,
and the two groups. A loss track keys on its `LossTrack`, as it does today.

**The option.** `--layout` takes `process` or `merged`, defaults to `process`
and reads `GCMON_LAYOUT`, which stops the run on any value but `process` or
`merged`, as `GCMON_FORMAT` does (ADR-0021). With a format other than
`perfetto` the configuration echo logs a warning and the run goes ahead, as it
does for `--rss`. The check compares the format with `perfetto` and adds no
tuple beside `RSS_CAPABLE_FORMATS`.

**Docs.** `docs/cli.md` documents the flag and the variable, `docs/formats.md`
the rows a merged trace holds, `docs/perfetto-sql.md` how to select one
process's pauses in it, and `docs/rss.md` where the counter sits, and under
which name, in each layout.

## 5. Seams and testing decisions

- **Seam:** the Perfetto integration suite in
  `tests/exporters/perfetto_integration/`: a trace built through the real
  `PerfettoExporter` with the merged layout and read back through the trace
  processor (ADR-0014). Row order, parentage and lanes come from
  `_track_event_tracks_ordered_groups`, a row's lanes being its `track_ids`;
  nesting comes from the `slice` table's `parent_id`.
- **New seam needed:** none; the layout is a constructor argument.
- **What makes a good test here:** what the trace processor draws, never the
  bytes. `misplaced_end_event` is filed under `data_loss`, so a check
  filtering on `error` alone misses it.
- **Prior art:** `TestTheOrderRowsAreDrawnIn` in `test_row_contents.py` for
  row order, `test_process_rows.py` for reading a merge through `track_ids`,
  `test_perfetto_process_span_fuzz.py` for the fuzz.
- **Cases:**
  1. The root rows are `All GC Pauses`, `GC Loss`, `Marks`, `Processes` and
     `RSS`, in that order, and the trace holds no process row with `pid > 0`.
  2. `All GC Pauses` holds `Gen0`, `Gen1` and `Gen2` in rank order.
  3. Two interpreters pausing over overlapping intervals: `Gen0` is one row
     whose `track_ids` hold two tracks, each pause keeps its own width, each
     sub-phase's `parent_id` is its own pause, and no `misplaced_end_event`.
  4. Two interpreters' overlapping loss windows: `GC Loss` is one row whose
     `track_ids` hold two tracks, and one interpreter's touching windows still
     read as a sequence.
  5. Pauses, loss windows and marks carry `pid` and `pid_epoch`; sub-phases do
     not.
  6. `RSS` holds a counter per process, in the order the process layout ranks
     its process rows.
  7. **Both layouts hold the same data**, built from the same events. What
     each draws directly matches in both directions: the same number of
     pauses, sub-phases, loss windows, marks, spans and RSS samples, each with
     the same width, name and args, `pid` and `pid_epoch` aside. What the
     process layout derives is recomputed from the merged trace: every
     per-generation counter and `heap_size` sample from the args of the pause
     that starts or ends at its timestamp, every `Lifetime` count from the
     process's pauses and loss windows.
  8. The process layout's trace is byte-identical to today's for the same
     events.
  9. `--layout merged --format jsonl` warns and runs; `GCMON_LAYOUT=bogus`
     stops the run.
  10. Marked `fuzz`: random overlapping pauses with sub-phases, across
      interpreters and processes, each pause read back at its own width with
      its sub-phases' `parent_id` naming it, and no `misplaced_end_event`.

## 6. Out of scope

- **`gcmon combine`.** The merged layout is unproven on real runs, and
  `combine` can take `--layout` once live runs show the shape holds. A
  combined trace stays in the process layout.
- **Converting a merged trace to the process layout.**
  [Spec 0073](0073-convert-a-merged-trace-to-the-process-layout.md) covers it;
  case 7 pins the property it rests on.
- **`gcmon report` reading a merged trace.**
  [Spec 0061](0061-build-the-statistics-table-from-a-tracefile.md) builds its
  reader around the process layout, and teaching it the merged one is 0061's
  work.
- **Choosing the layout from the tree's size.** gcmon is a streaming writer
  and does not know how wide a tree will grow when it writes the first
  descriptor, the argument ADR-0024 and ADR-0027 already make.
- **A `heap_size` chart in the merged layout.** Its values are on the pauses,
  and a chart means a row per interpreter, the shape this layout exists to
  avoid.
- **The records.** The ADRs in the header are amended once this lands, with a
  new record taking the decision; each bullet names the clause it loses.
