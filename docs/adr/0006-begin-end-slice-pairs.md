# ADR-0006: Represent durations as Begin/End pairs in both backends

- **Status:** Accepted
- **Date:** 2026-06-14

## Context

The Chrome Trace Event format offers two ways to express a span. A "complete" event
(`ph: "X"`) carries a start timestamp and a duration in one record. A begin/end pair
(`ph: "B"` / `ph: "E"`) carries two records with two timestamps.

gcmon's Chrome backend emitted `ph: "X"` with `ts` + `dur`. The Perfetto backend emitted
`TYPE_SLICE_BEGIN` / `TYPE_SLICE_END` pairs from the *same* `TGCStatsInfo` fields, because
Perfetto has no complete-event primitive.

The result was an impedance mismatch sitting between two backends that were otherwise
computing the same thing. Each had its own copy of the GC sub-phase discovery logic (the
`has_*` guards for mark-alive, deduce-unreachable, handle-weakrefs, and the rest), the same
name and category strings, and its own arithmetic: one converting a pair of timestamps into
`ts + dur`, the other keeping them apart. Sharing that logic was impossible while the two
sides disagreed on the shape of a span.

## Decision

The Chrome backend emits begin/end pairs. `ph: "X"` is not produced.

- The `PauseEvent` / `IncrementalEvent` types and their `pause_event()` / `inc_event()`
  factories are replaced by `BeginEvent` / `EndEvent` and `begin_event()` / `end_event()`.
- `convert_item_to_trace_format` emits a begin/end pair per span rather than a single
  complete event.
- The Chrome trace reader parses `ph: "B"` and `ph: "E"`; `ph: "X"` parsing is removed.
- Timestamp normalization covers `"B"`, `"E"`, `"C"` and `"I"` events.

Begin/end is the shared primitive. Perfetto's model wins because it is the one that cannot
be expressed in terms of the other: a complete event is derivable from a pair, but a pair
carrying independent metadata at each end is not derivable from a complete event.

## Consequences

- This was the enabling step for [ADR-0007](0007-shared-trace-converter-pipeline.md): with
  both backends agreeing on the primitive, the sub-phase discovery logic and the naming
  strings collapsed into one shared converter.
- The Chrome output has roughly twice as many event records for the same spans. The files
  are larger; `chrome://tracing` and the Perfetto UI both render begin/end pairs natively,
  so nothing downstream had to change.
- A truncated or interrupted Chrome trace can end with an unmatched `"B"`. Both viewers
  tolerate this; a complete event could never be half-written.
- The Chrome converter no longer calls `dur_to_us`. Duration is a property of the pair,
  not of a record.

## Alternatives considered

- **Make Perfetto synthesize complete events.** Not possible; the format has no such
  primitive.
- **Keep both shapes and translate at the boundary.** Rejected: that relocates the
  impedance mismatch without removing it, and it keeps the duplicated sub-phase logic that
  cost the most.

## Implementation

- `src/gcmon/trace_event.py`, `BeginEvent` / `EndEvent` and the `begin_event()` /
  `end_event()` factories.
- `src/gcmon/exporters/trace_converter.py`, which emits the pairs.
- `src/gcmon/exporters/chrome_trace_io.py`, where `_parse_events` handles `"B"` / `"E"`
  and `_normalize_trace_timestamps` collects `"B"`, `"E"`, `"C"`, `"I"`.
- `tests/helpers.py`, `assert_is_begin` / `assert_is_end`.
