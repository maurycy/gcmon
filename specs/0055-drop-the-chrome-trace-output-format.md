# 0055: Write one trace format, and drop the Chrome Trace format

- **Status:** Not started
- **Kind:** feature (cleanup)
- **Effort:** L
- **Origin:** maintainer decision, 2026-08-21
- **Pinned** by `tests/monitoring/test_monitored_run_trace.py`, which pins a whole run to the
  Chrome encoder's bytes; section 5 moves that seam to the Perfetto leg rather than deleting it
- **Respects:** [ADR-0001](../docs/adr/0001-hand-rolled-perfetto-protobuf-encoder.md) (gcmon
  hand-rolls the protobuf, so something has to check it),
  [ADR-0007](../docs/adr/0007-shared-trace-converter-pipeline.md) (one converter,
  `list[TraceEvent]` between it and the encoders),
  [ADR-0008](../docs/adr/0008-buffered-exporter-and-encoder-protocol.md) (exporter buffers, encoder
  serializes), [ADR-0013](../docs/adr/0013-rss-sampling.md),
  [ADR-0018](../docs/adr/0018-stats-requires-a-view-and-keeps-no-bare-alias.md) (an option's
  environment variable takes the option's words, and refuses anything else)
- **Overturns** [ADR-0012](../docs/adr/0012-trace-output-formats.md), whose dual-output half and
  whose conversion matrix both go, and the parametrization half of
  [ADR-0014](../docs/adr/0014-perfetto-integration-test-strategy.md). Section 4.6 says which is
  superseded and which is amended

## 1. Problem statement

gcmon writes two trace formats for one run, and only one of them is worth opening. The Chrome Trace
Event format carries no command lines
([ADR-0010](../docs/adr/0010-process-identity-cmdline-and-start-marker.md)), no `Processes`
minimap, no counter Y-axis sharing, no process ordering and no `Start Process` marker; its
timestamps are microseconds, so every trace loses three digits of precision to an integer division
([ADR-0009](../docs/adr/0009-nanoseconds-canonical-time-unit.md)). `docs/formats.md` already
documents Chrome as the format missing those five things.

It is also the default. An operator who runs `gcmon monitor 12345` and nothing else gets
`gcmon.json`, the weaker of the two files, and finds out what it does not contain when they go
looking for a command line in the UI.

The encoder itself is forty lines. The cost sits around it, in the machinery that exists because
there are two of them: a `chrome+perfetto` fan-out exporter that reads a private attribute off each
sub-exporter (spec 0028), a `combine` matrix with a rejected cell in it, an `RSS_CAPABLE_FORMATS`
tuple in the CLI layer naming three of its four entries after Chrome (spec 0036), a README example
headed "Chrome Trace Output" and captioned as the Perfetto UI (spec 0031), and about 1,800 lines of
test.

## 2. Solution

`gcmon monitor 12345` writes `gcmon.pftrace` and you open it in `ui.perfetto.dev`. The formats are
`perfetto`, `jsonl` and `stdout`, and `--format chrome`, `--format trace` and `--format
chrome+perfetto` are gone: argparse rejects them by name and lists what is left. `GCMON_FORMAT`
takes the same three words, and a fourth stops the run rather than quietly substituting one.

`gcmon combine` reads JSONL and writes JSONL or Perfetto. It no longer takes `--input-format`,
because JSONL is the only input, and it no longer has a combination it refuses. Handed a Chrome
file from an earlier release, it says so by name instead of reporting malformed JSON.

Nothing about the JSONL format changes, and nothing about what a Perfetto trace contains changes.
An operator holding a `.json` file from an earlier release keeps something the Perfetto UI still
opens; what they lose is the ability to produce another one, or to feed that one back through
`combine`.

## 3. User stories

1. As an operator attaching to a production process, I want the default output to be the format
   that carries command lines and process spans, so that the file I take away from a one-off
   session is the complete one.
2. As a developer profiling a script under `gcmon run`, I want `--format` to offer only formats
   gcmon supports, so that I cannot pick the weaker one by typing the word I remember from the
   README.
3. As an operator who scripted `--format chrome`, I want the run to fail at the argument, naming
   the formats that exist, rather than to write a file I would later find is not what I asked for.
4. As an operator with `GCMON_FORMAT=chrome` exported in my shell, I want the run to stop and name
   the value, so that I am not handed a different format than the one I configured without being
   told.
5. As an operator with a JSONL capture from last month, I want `gcmon combine --output-format
   perfetto` to read it unchanged, so that this is not a migration of my archive.
6. As an operator with a `.json` file from an earlier release, I want `combine` to tell me it is a
   Chrome trace gcmon no longer reads, so that I do not read a parse error as a corrupt file.
7. As someone reading a trace in the Perfetto UI, I want the trace to contain exactly what it
   contains today, so that my saved queries keep working.
8. As a CI job asserting on `gcmon.json`, I want the default output path to change in a release
   that says so in its breaking changes, so that the failure is one line to fix.
9. As someone importing `gcmon.TraceExporter`, I want the name to disappear from the public surface
   in a release that says so, so that I get an `ImportError` at the import rather than at the first
   call.
10. As a maintainer of the hand-rolled protobuf encoder, I want a check that reads a trace back
    against the events it was built from, so that a wrong field number is caught by something other
    than an expectation written from the same code.
11. As a maintainer adding an output format, I want one encoder implementation to model on rather
    than two that differ in their file-mode handling, so that the contract `EventEncoder` states is
    the one the code demonstrates.
12. As a maintainer, I want the `chrome+perfetto` fan-out and its two `# type: ignore` comments
    gone rather than fixed, so that spec 0028 retires without being implemented.

## 4. Implementation decisions

### 4.1 What goes, and what `--format` becomes

Deleted outright: `exporters/chrome_trace_exporter.py` (`TraceExporter`),
`exporters/chrome_trace_format.py` (a re-export shim ADR-0007 left behind),
`exporters/combined_exporter.py` (`CombinedTraceExporter`, `derive_combined_paths`), and
`JsonEventEncoder` from `exporters/encoder.py`. `EventsExporterFactory` loses three `match` arms,
including the `trace` alias that only that `case` documented.

`TraceExporter` leaves **two** `__all__` lists: `gcmon.exporters.__all__` and `gcmon.__all__`. The
second is the public surface, which 0041 was careful to leave unchanged, so this one is a breaking
change and gets a line of its own.

`--format` takes `perfetto`, `jsonl`, `stdout`, defaulting to `perfetto`, in
`cli/commands/monitoring_options.py`. `get_env_output` returns `Path("gcmon.pftrace")`, keeping its
existing `jsonl` special case, so the three defaults stay `gcmon.pftrace`, `gcmon.jsonl` and no
file.

**`GCMON_FORMAT` refuses a word `--format` would refuse.** `get_env_format` stops whitelisting and
hands its value on as written, the way `get_env_stats` already does; `get_monitoring_options`
refuses anything outside the three and returns `None`, which stops the run, once logging is
configured. ADR-0018 settled this shape for `--stats`, and the same asymmetry it fixed is here:
today `GCMON_FORMAT=chrome` would silently become `perfetto` and `get_monitoring_options` would log
`Format: perfetto`, echoing a rejected configuration as though it had accepted it, which is spec
0040's complaint. argparse leaves a string default alone rather than checking it against `choices`,
so the raw value reaches the validator instead of dying in the parser.

`RSS_CAPABLE_FORMATS` becomes `("perfetto",)`. It does not go away here: spec 0036 removes the
tuple by asking the exporter instead, and shrinking it is the smaller change that does not preempt
that one.

`ts_to_us` in `support/time_units.py` had one caller, `JsonEventEncoder`. It goes, with its test.
ADR-0009's decision that `TraceEvent.ts` is nanoseconds stands; what it loses is the one encoder
that converted.

**Rejected: keeping the words in the whitelist for one release so that `--format chrome` exits 1
with a message.** It buys a better error for anyone who scripted the flag, at the cost of a format
name that exists in three files and produces nothing. The breaking-changes entries are the notice,
and argparse names the three formats that remain.

### 4.2 `combine` reads JSONL only, and says so

`combine_files` in `exporters/combine.py` drops its `input_format` parameter. `_parse_events` and
`_normalize_trace_timestamps`, which existed to read and renormalize Chrome JSON, go with it. What
remains is two paths, both keyed on `output_format` alone:

| output | path |
|---|---|
| `jsonl` | `read_jsonl`, merge, `normalize_jsonl_timestamps`, `write_jsonl`, unchanged |
| `perfetto` | `read_jsonl`, `convert_to_trace_format` per file, `ProtobufEventEncoder` |

Per-file normalization on the Perfetto path and whole-merge normalization on the JSONL path both
stay as they are; ADR-0012 records why they differ, and that half of it survives.

**A Chrome file is named, not parsed.** `read_jsonl` in `exporters/jsonl_io.py` checks whether the
first non-blank line begins with `[`, and raises with a message saying the file is a Chrome trace,
that gcmon no longer reads one, and that the Perfetto UI still opens it. The check lives in the
reader rather than in `combine_files` so that every caller of `read_jsonl` gets it, the pyperf
hook's replay included. `msgspec.DecodeError` subclasses `ValueError`, which is what `cmd_combine`
already catches, so the message reaches the operator through the path that exists; without the
check it would be msgspec's own complaint about line 1, which reads as a corrupt file.

`--input-format` is removed from the `combine` parser rather than reduced to one choice. A flag
with a single value is a question with one answer, and leaving it would keep `combine
--input-format chrome` a spelling argparse accepts. The `chrome` to `jsonl` rejection is deleted
from both places that carry it today, `cmd_combine` in `cli/commands/convert_cmd.py` and
`combine_files`, which removes the duplicated validation spec 0030 counts among its six hazards.

`--output-format` keeps `jsonl` and `perfetto` and defaults to `perfetto`, matching the live
default.

### 4.3 The intermediate keeps its shape

`model/trace_event.py` stays as it is. Its structs are Chrome-shaped, `ph`, `cat` and a `ts` the
Perfetto converter reads as nanoseconds, and after this change their only consumer is
`perfetto_format.convert_trace_events_to_perfetto`. That is ADR-0007's `list[TraceEvent]` seam
doing its job, and reshaping it is a change to the converter, the track state, the loss-slice
builder and every `test_perfetto_*` module, for no operator-visible gain.

The module docstring changes. It opens "Chrome Trace Format events, and the factories that build
them", and after this it would name a format gcmon does not write; it names the seam instead, the
events every output format is built from. The comment above `RSS_TID` explains the sentinel tids
through the Chrome format's `(pid, tid)` track identity, which is why those numbers are what they
are. It keeps the reference and gains the tense that marks it as history.

**The follow-up this defers:** whether `TraceEvent` should be reshaped around Perfetto's own
vocabulary once nothing else reads it. What settles it is spec 0036, which rewrites the exporter
interface above this seam; taking both at once means changing the producer and the consumer of the
intermediate in one step. Section 6 keeps it out.

### 4.4 The encoder protocol stays

`EventEncoder` keeps its three methods and its one remaining implementation, and `PerfettoExporter`
stays a thin subclass of `BufferedTraceExporter`. ADR-0008 split them for two reasons, and only one
of them was "two formats": the other was that `combine` drives `ProtobufEventEncoder` directly,
with no exporter, no buffer and no lock. `combine` still does that, so the composition still earns
its keep.

`PerfettoExporter.__init__` gains a `sequence_id` keyword and forwards it to the encoder, which
already takes one and otherwise derives it from `id(self)`. That is the same shape
`cmdline_provider` has, and section 5 says which test needs it.

**Rejected: folding `ProtobufEventEncoder` back into `PerfettoExporter` now that one format is
left.** It would put `combine`'s Perfetto output back inside an exporter's lifecycle, which
ADR-0008 rejected, and ADR-0008's "a new output format is an `EventEncoder` implementation" is the
contract a future format arrives through.

### 4.5 The specs this retires

- **0028** (`chrome+perfetto` reads a private attribute) retires **Superseded** by this spec: the
  exporter it describes is deleted. Its `output_path` argument does not survive on its own, since
  no caller is left that needs to ask an exporter where it writes.
- **0031** (README example headed "Chrome Trace Output", captioned as the Perfetto UI) retires
  **Superseded**: section 4.6's README pass rewrites the heading this change makes wrong anyway.
- **0036** and **0030** keep their files. Each loses one item, named above.

### 4.6 Documents

The decision gets **ADR-0021**, "Write one trace format", which carries forward the half of
ADR-0012 that survives: `combine --output-format perfetto`, the per-file against whole-merge
normalization split, Perfetto not being accepted as an input, and `-o` being used verbatim.
ADR-0012's status becomes `Superseded by ADR-0021`, the two link both ways, and its text is left
alone.

Amended in place, because each states something about the code that stops being true: **ADR-0006**
(begin/end pairs "in both backends"), **ADR-0007** (the re-export shim, and the chrome-perfetto
equivalence tests it cites), **ADR-0008** (two encoder implementations), **ADR-0009** (the encoder
that divides by 1000), **ADR-0013** (which formats carry RSS), and **ADR-0014**, whose "tests are
parametrized over Chrome JSON and Perfetto binary" is the parametrization this removes; its
equivalence test survives in the form section 5 gives it. Their Context sections are history and
stay as written; the Decision, Consequences and Implementation sections lose the present tense
about Chrome.

`CONTEXT.md` gains **Trace**, beside Event, which already leans on the word without defining it,
and against the three synonyms in circulation across the docs and the ADRs: timeline, profile,
output file. `Tracefile` and `trace file` are named there as interchangeable spellings rather than
ruled out. **No matching entry for the JSONL side**: Record and Event already carry the distinction
that matters, a container noun for each follows from them, and the one-way direction of `combine`
is not a domain rule but two unrelated implementation facts, one of which this spec deletes and the
other of which ADR-0001 records.

`docs/formats.md` opens on three formats, and its "Chrome trace and Perfetto output" section
becomes one section about the trace, with the "Perfetto adds" list folded into the one above it and
the Chrome sentence under "Process command lines" cut. `docs/cli.md` loses Chrome from four tables
and its two `gcmon.json` defaults. `docs/README.md` says three formats. `README.md` drops Chrome
from its feature list and its opening line, heads its example "Perfetto Trace Output", and updates
the `gcmon monitor` example's comment.

`CHANGELOG.md` gains five lines under `### Breaking changes` in `## WIP`: the formats that are
gone, the default output that moved from `gcmon.json` to `gcmon.pftrace`, `combine` losing
`--input-format`, `GCMON_FORMAT` refusing a word `--format` refuses, and `gcmon.TraceExporter`
leaving the public surface. The removal work itself is internal and joins the standing line.

## 5. Seams and testing decisions

- **Seam:** the CLI, for the formats that no longer exist; `read_jsonl`, for the Chrome file an
  operator still has; and `tests/monitoring/test_monitored_run_trace.py` for the whole-run
  characterization the Chrome fixture holds today.

- **New seam needed:** none, but the pinned test **moves to the Perfetto leg** and its fixture
  changes form. Its docstring gives the current reason for pinning Chrome: Perfetto's
  process-lifetime sweep clips spans by the order liveness arrives in, and Chrome drops liveness on
  a base-class no-op and resolves no cmdline. Both are injectable rather than inherent, once
  `PerfettoExporter` forwards `sequence_id` (section 4.4): that keyword fixes the only
  nondeterministic value in a trace, and `cmdline_provider` takes a stub returning `None`, which
  keeps psutil out. Building the encoder directly instead is not an option, because
  `add_process_liveness` is overridden on `PerfettoExporter` alone, so the base's no-op would
  swallow liveness and the `Processes` track would come out empty. The scripted clock feeds the
  liveness order, and `test_the_clock_was_spent_exactly` already guards that clock.

**The fixture stores decoded packets, not bytes.** Serialize the run, decode every `TracePacket`
through `perfetto_trace_pb2`, and pin the text form. That keeps the property the Chrome fixture was
chosen for, a per-event diff a human reads, and it asserts more than the bytes did: decoding
through Perfetto's own generated schema reads each field back through a field number gcmon did not
supply, which is the failure ADR-0001 and ADR-0014 exist for and the one a same-constant round trip
cannot see (CONVENTIONS rule 6). The regeneration entry point and the "never regenerate to clear a
red run" instruction carry over verbatim.

- **The encoder's oracle is rebuilt, not dropped.** `TestEquivalence` in
  `tests/test_convert_cmd_perfetto.py` is the only check that reads gcmon's protobuf through a code
  path gcmon did not write and compares it against a trace built by a different encoder: both sides
  share `convert_to_trace_format` and then diverge, one through `JsonEventEncoder` and the trace
  processor's JSON reader, one through `ProtobufEventEncoder` and its protobuf reader. Everything
  else in the `test_perfetto_*` suite compares a trace against expectations a human wrote from the
  same code, which cannot catch an error the two share. ADR-0001 is why that matters.

It is rewritten to compare the trace processor's reading of the `.pftrace` against the
`list[TraceEvent]` it was built from: slice names, durations in nanoseconds, and arg keys and
values, with the `debug.` prefix applied to the event's own arg names. The events become the oracle
instead of a second format, which is the same cross-check with one fewer format in it and keeps
working for whatever format arrives next.

**Rejected: keeping `JsonEventEncoder` in `tests/` as the oracle.** It keeps the format gcmon just
dropped alive under a different roof, and makes the trace processor's JSON reader a test dependency
for something nothing ships.

- **What makes a good test here:** for the removal itself, assert the operator's outcome and not
  the absence of a symbol. `gcmon monitor --format chrome` exits 2 and names the formats that
  exist. `gcmon monitor 12345` with no `--format` writes `gcmon.pftrace`.

- **Prior art:** `tests/test_cli.py` and `tests/monitoring/test_monitoring_options.py` for argparse
  rejection and for the `--stats` env-var refusal this copies; `tests/test_convert_cmd_perfetto.py`
  for the `combine` matrix; `tests/exporters/perfetto_helpers.py` for decoding a packet through
  `perfetto_trace_pb2`.

- **Cases:**
  1. `--format chrome`, `--format trace` and `--format chrome+perfetto` each exit 2, and the
     message names `perfetto`, `jsonl`, `stdout`.
  2. `GCMON_FORMAT=chrome` stops the run with a message naming the value, and `GCMON_FORMAT` unset
     still gives `perfetto`.
  3. A default `monitor` run writes `gcmon.pftrace` and no `gcmon.json`.
  4. `combine` handed a Chrome file reports it as a Chrome trace and exits 1, and the message does
     not say the JSON is malformed.
  5. `combine` rejects `--input-format` as an unknown argument, and combining JSONL to Perfetto and
     to JSONL produces what it produces today.
  6. Regression guard: the whole-run fixture, moved to Perfetto, and the `test_perfetto_*` suite
     unchanged. A trace's contents must not move by one field in a change that only removes another
     format.

- **Three suites reach a claim through the Chrome leg and get ported, not deleted.** Each asserts
  something that stays true with one format left, so deleting it would drop the assertion along
  with the format.

  `tests/exporters/test_combine_loss_round_trip.py` walks the combined output, parsing the Chrome
  JSON and resolving BEGIN/END as a stack the way a trace processor does, because a span emitted
  after the one it should precede reads as nested and every field-by-field assertion passes on a
  file whose lines were shuffled. ADR-0015 names that depth as the one place the mistake shows.
  It is rebuilt to resolve the combined spans through the trace processor instead, which is a
  rewrite of the walk rather than a changed argument; the live side from `loss_row` is untouched.

  `tests/exporters/test_perfetto_exporter_integration.py` is parametrized over `chrome` and
  `perfetto` across five classes, which is the parametrization ADR-0014 records. It keeps the
  Perfetto leg and loses the parameter, the format-keyed arg-prefix dict and the branch choosing
  `trace.json` or `trace.pb`.

  `tests/exporters/test_exporter_thread_safety.py` runs its concurrency claims over a list of
  exporter factories, one of them `_ChromeTraceExporterFactory`, and carries two Chrome-only
  tests for a race the base class arbitrates. The factory leaves the list. The two tests go, since
  the Perfetto and JSONL factories already cover that race through the same base class.

- **`tests/exporters/test_buffered_exporter.py` changes encoder rather than losing cases.** It
  tests `BufferedTraceExporter` itself and reaches for `JsonEventEncoder` only as something to
  instantiate the base with. It takes `ProtobufEventEncoder` instead and keeps every case.

**Deleted with the format:** `tests/exporters/test_chrome_trace_exporter.py`,
`test_chrome_trace_format.py`, `test_combined_exporter.py`,
`test_combined_exporter_integration.py`, the Chrome half of `test_combine.py` and
`test_convert_cmd.py`, the `chrome -> perfetto` input class in `test_convert_cmd_perfetto.py`, the
Chrome assertions and `ChromeTraceValue` in `tests/helpers.py`, the `trace_exporter` fixtures in
`tests/exporters/conftest.py`, and `tests/fixtures/monitored_run_chrome_trace.json`.

## 6. Out of scope

- **Reshaping `TraceEvent`.** Section 4.3 states the decision and what would settle the follow-up.
  Doing it here would put the converter, the track state, the loss-slice builder and every
  `test_perfetto_*` module into a change that is otherwise a subtraction.
- **Converting an existing Chrome file to a trace.** It is the `_parse_events` path this deletes,
  kept alive for one purpose. `combine` names the file instead, and the Perfetto UI still opens it,
  which is what anyone would convert it for.
- **Implementing 0028's `output_path` property.** Section 4.5 retires that spec rather than landing
  it.
- **Removing `RSS_CAPABLE_FORMATS`.** Spec 0036 owns that tuple's removal; this shrinks it to one
  entry.
- **`--format` learning to derive its output extension.** `-o` is used verbatim today, ADR-0012
  records why, and ADR-0021 carries that forward. Only the default path changes.
- **Renaming `--format`,** now that one of its three values is a trace and two are JSONL. Spec 0040
  rewrites the option declarations and is where a rename would cost least.
- **Deprecating JSONL.** Untouched. It is the only lossless thing gcmon writes and the only input
  `combine` reads.
