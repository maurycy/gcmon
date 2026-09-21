# 0030: Three hygiene items in the exporter package

- **Status:** Not started
- **Kind:** feature (cleanup)
- **Effort:** S
- **Origin:** post-v0.2.0 code review (old spec 18, REQ-2, 7, 9, 10, 11, 12,
  14)
- **Respects:**
  - [ADR-0003](../docs/adr/0003-gc-metrics-group-track.md): a rank on a child
    of the process track is discarded, so `rss` stays out of the table.
  - [ADR-0005](../docs/adr/0005-counter-y-axis-share-key.md): the share key is
    the metric name and there is no lookup table; the same reasoning is why
    the rank table holds only metrics a record can carry.
  - [ADR-0008](../docs/adr/0008-buffered-exporter-and-encoder-protocol.md):
    one lock guards the buffer and every touch of encoder state, so the
    encoder's caller is what serializes `PerfettoTrackState`.
  - [ADR-0027](../docs/adr/0027-group-every-row-an-interpreter-owns.md): the
    order of the rows in a group is the record's decision, so the test spells
    it out rather than reading the tuple back.
  - [ADR-0029](../docs/adr/0029-report-liveness-and-fold-it-into-the-span.md):
    `add_process_liveness` takes `_io_lock` explicitly for this reason.

## 1. Problem statement

Three independent changes, batched because each is too small to schedule alone
and all three live in the exporter package. Two more went with the Chrome
format ([0055](RETIRED.md)): the `getattr` probe was in its encoder, and the
duplicated format validation had nothing left to disagree about once `combine`
took one input. A third, 4.3, went with the code it was about, and most of 4.1
went with ADR-0027. None is operator-visible today; each is a way for a future
change to go wrong quietly. Take them together or drop any one; nothing here
depends on anything else here.

## 2. Solution

No operator-visible change. Every item here is internal.

## 3. User stories

1. As a maintainer adding a counter metric, I want one place that says where
   it draws and a test that states the order, so that adding one is a single
   edit and reordering the group cannot pass unnoticed.
2. As a maintainer touching `PerfettoTrackState`, I want its threading
   contract written down, so that I do not add a call from outside the encoder
   and corrupt uuid allocation.
3. As anyone reading `build_track_event`, I want its parameters not to shadow
   builtins, so that `type()` means `type()` inside the function.

## 4. Implementation decisions

**4.1: the rank table holds only metrics a record can carry, and a test states
their order.** Most of this item landed with ADR-0027: the hand-written dict
became `_COUNTER_ORDER`, a tuple whose index is the rank, and the fallback
became `_UNLISTED_COUNTER_RANK`, which draws a metric nobody listed below
every listed one rather than above them. Two things are left.

Five of the nine entries rank rows gcmon cannot draw.
`convert_item_to_trace_format` builds `counter_data` from `COLLECTED`,
`CANDIDATES`, `DURATION` and, when it is non-zero, `UNCOLLECTABLE`, which is
`GEN_COUNTER_METRICS`; `INCREMENT_SIZE`, `ALIVE_SIZE`,
`FINALIZED_GARBAGE_COUNT`, `DELETED_GARBAGE_COUNT` and `CLEAR_WEAKREFS_COUNT`
reach the trace as annotations on the pause slice, and nothing else builds a
`Counter` but the `heap_size` line beside it and `add_rss_sample`. Cut those
five. The four that remain keep ranks 0 to 3, so no trace byte moves, and
`_UNLISTED_COUNTER_RANK` falls from 9 to 4, which only a metric nothing emits
could observe. ADR-0005 rejected a lookup table for share keys because it
needs an edit whenever someone adds a metric; ranks for metrics that do not
exist are that edit, paid in advance for a case nobody has.

The order of the four is asserted nowhere.
`test_duration_counter_in_gc_metrics_group` checks `duration`'s rank against
`_COUNTER_RANKS[DURATION]`, which reads the rank out of the table and compares
it to itself. Spell the four out by name instead, the way
`TestTheRowsInsideAnInterpreterGroupAreRanked` spells out the rows of an
interpreter group, and drop that assertion: its test is about the counter's
parent being `GC Metrics`, which the two lines under it already assert.

**4.2: `PerfettoTrackState` states its threading contract.** It has no class
docstring at all. It is not internally thread-safe and does not need to be:
its only caller is `ProtobufEventEncoder`, and every entry point there runs
under whatever serializes the encoder: `PerfettoExporter._io_lock`, which each
`add_*` and `close` takes, or nothing at all in `combine`, which is
single-threaded. What a maintainer needs is the rule that follows: no lock
here, and no call from outside the encoder. No locking, no behaviour change.

The exporter's own locking is settled in ADR-0008, so 4.2 documents
`PerfettoTrackState` alone.

**4.3: dropped, 2026-08-26.** It asked `BufferedTraceExporter._build_meta` to
state the atomicity of its check-and-emit. There is no such method: no
producer decides what a batch's descriptors are any more
([ADR-0024](../docs/adr/0024-an-event-names-the-track-it-is-drawn-on.md)), and
no such class either
([ADR-0008](../docs/adr/0008-buffered-exporter-and-encoder-protocol.md)). The
guarantee it wanted written down is now `PerfettoTrackState`'s, which is what
4.2 covers. `TestMetaDedupRaceClosed` still stands and says in its own
docstring that the race closed by deletion. The number is kept rather than
reused, so 4.4 stays 4.4.

**4.4: `build_track_event` stops shadowing `type`.** Rename its first
parameter to `event_type`. It is re-exported from `perfetto_format` and called
from `perfetto_format`, `perfetto_builders` and `perfetto_process_lifetime`,
and it is called by name in the tests, so grep `src/` and `tests/` together.
Mechanical, but it is a keyword-argument rename and will fail loudly rather
than silently if a call site is missed.

**Not adopted at all:** importing `psutil` at the top of the module that reads
a command line, and making it a hard dependency. Graceful degradation without
`psutil` is a documented, tested property: the `[cmdline]` extra in
[docs/rss.md](../docs/rss.md), the fallback in
`gcmon.monitoring.process_registry`, and the same pattern in `rss_sampler`.
The lazy import is what makes it work.

## 5. Seams and testing decisions

- **Seam:** `tests/exporters/`, at each module's public function. Nothing here
  changes what a trace means, so the trace-processor seam has nothing to
  observe; the existing integration suite serves as the regression guard
  rather than the assertion.
- **New seam needed:** none.
- **What makes a good test here:** for 4.1, name the four metrics and their
  order in the test, so the test fails if the tuple is reordered. A test that
  reads the ranks out of the tuple and compares them to itself proves nothing,
  which is what the assertion 4.1 drops does. 4.2 and 4.4 are covered by the
  existing suite continuing to pass; do not add tests that assert a docstring
  exists.
- **Prior art:** `TestTheRowsInsideAnInterpreterGroupAreRanked`, whose
  docstring states why the order is spelled out rather than read back.
- **Cases:**
  1. The four counters inside `GC Metrics` draw in their listed order, named,
     at ranks 0 to 3.
  2. A metric nobody listed still draws below every listed one, which
     `test_a_metric_nobody_listed_draws_below_every_listed_one` already
     asserts and which the cut leaves standing.
  3. Regression guard: the full Perfetto integration suite passes unchanged:
     no track moves, no field number changes.

## 6. Out of scope

- Anything that changes trace bytes. Every item here is internal.
- `psutil` as a hard dependency (see section 4, not adopted).
- Splitting `perfetto_format`, which is large enough to deserve it but not as
  part of a hygiene pass.

## 7. Further notes

[0033](0033-loss-counter-track.md) draws its lane inside `GC Metrics`, so
after 4.1 it adds its metric to `_COUNTER_ORDER` and to the test. That second
edit is the point: today a lane nobody listed draws last and says nothing.
