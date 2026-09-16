# ADR-0008: Split exporters into a buffering base class and a pluggable `EventEncoder`

- **Status:** Accepted
- **Date:** 2026-06-14
- **Amended by:** [ADR-0021](0021-write-one-trace-format.md),
  [ADR-0024](0024-an-event-names-the-track-it-is-drawn-on.md)

## Context

`TraceExporter` (Chrome) and `PerfettoExporter` each independently implemented
the same lifecycle: a two-lock model (one for state, one for I/O),
`flush_threshold`-based buffering, the `add_event` / `add_instant_event` /
`close` sequence, and per-pid/iid deduplication of `ProcessMeta` /
`ThreadMeta`.

Only the byte production differed: the Chrome side's `[\n … \n]\n` bracket
dance versus the Perfetto side's `"wb"`-then-`"ab"` file-mode toggle. The two
exporters duplicated everything around it.

Both copies also carried the same bug. The meta-dedup did its "have I seen
this pid?" check and its emit in separate critical sections, so two threads
adding events for a brand-new pid could both pass the check and both emit a
`process_name` event, putting a duplicate process descriptor in the output.

## Decision

**`PerfettoExporter` owns the lifecycle:** the two locks, the buffer and flush
threshold, and `add_event` / `add_instant_event` / `close`.

**`EventEncoder`** (a `Protocol` in `encoder.py`) owns format-specific byte
production through three methods: `open(path)`, `write_events(events)`,
`close()`. `ProtobufEventEncoder` is its one implementation
([ADR-0021](0021-write-one-trace-format.md)), and the protocol stays because
`combine` drives the encoder with no exporter around it.

The exporter constructs its encoder, and its public constructor signature is
unchanged.

**The `EventEncoder` protocol stays declared, and is typed against nothing.**
Both callers -- `PerfettoExporter` and `combine` -- name
`ProtobufEventEncoder`. What ADR-0021 defended when it kept this split is the
encoder being a separate class that runs with no exporter, no buffer and no
lock around it, and dropping the base left that untouched. Whether a protocol
with no annotation left still earns its declaration is a separate question,
and open.

**Meta building is atomic.** The check and the emit happen inside a single
critical section under the state lock, closing the race. This is the property
the two previous implementations were reaching for and missing.

The split settled three further questions:

- **One place holds the seen-pid set**, `PerfettoTrackState` in the encoder
  ([ADR-0024](0024-an-event-names-the-track-it-is-drawn-on.md)). Exactly one
  `ProcessMeta` per pid reaches the wire, a cmdline is registered at most
  once, and nothing needs a double-checked-locking dance around that
  registration.
- **Cmdline registration ran under the I/O lock.** The old design ran the slow
  `psutil.Process(pid).cmdline()` call outside any lock to avoid serializing
  threads, which is what needed the double-checked locking. Moving it inside
  `write_events` cost one serialized call per pid. The monitor reads it now,
  once, where it creates the process
  ([ADR-0010](0010-process-identity-cmdline-and-start-marker.md),
  [ADR-0025](0025-create-every-process-in-one-place.md)), and the encoder only
  records what arrives.
- **`JsonEventEncoder` wrote `[]\n` on close only if nothing was ever
  written.** If any `write_events` succeeded it wrote `\n]\n` instead. Both
  paths produced a valid JSON array. `ProtobufEventEncoder` writes no file at
  all for a run with nothing in it.

## Consequences

- A new output format is an `EventEncoder` implementation. No lifecycle,
  locking or dedup code to copy. [ADR-0021](0021-write-one-trace-format.md)'s
  `combine --output-format perfetto` reuses `ProtobufEventEncoder` directly,
  outside any exporter, because the protocol has no dependency on the base
  class.
- Output bytes were unchanged by the refactor, verified by the existing
  structural tests, which decode the output and assert on each meaningful
  field.
- `close()` is idempotent.
- **`add_event` after `close()` silently drops the event.** This matches the
  pre-refactor behaviour, and the alternative is raising from a monitoring
  callback during shutdown.
- A cmdline provider failure costs the descriptor its cmdline and nothing
  else. A `psutil` error never costs you the trace.

## Alternatives considered

- **A buffering base class the exporters share.** What this record decided
  first, and rejected once [ADR-0021](0021-write-one-trace-format.md) left one
  exporter: the base had a fan-out of one. Meta building had moved to the
  encoder under [ADR-0024](0024-an-event-names-the-track-it-is-drawn-on.md),
  taking the seen-pid set and the atomic check-and-emit with it, so what
  remained to merge was a buffer, two locks and four one-line `_enqueue`
  calls. The second handle to the encoder went with it: that attribute existed
  only because the base held the encoder as an `EventEncoder`, and one class
  holds it at its own type.
- **A common base class with abstract encode methods instead of a separate
  protocol object.** Rejected: composition lets the encoder run without an
  exporter, which is what `combine` needs.
- **Keep cmdline registration outside the lock.** Rejected: it required the
  double-checked locking that atomic meta building makes unnecessary, and the
  call now happens once per pid, so the serialization is not worth the
  complexity.
- **Fold `JsonlExporter` / `StdoutExporter` into the same base.** Not done:
  they consume raw `TGCStatsInfo`, not `TraceEvent`, so the data shapes
  differ. This remains open work.
