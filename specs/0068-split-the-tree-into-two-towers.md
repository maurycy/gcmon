# 0068: Split the tree into two towers

- **Status:** Not started
- **Kind:** feature (cleanup)
- **Effort:** L
- **Origin:** design session 2026-09-02 on running two applications out of one
  source tree
- **Respects:** [ADR-0026](../docs/adr/0026-two-towers-over-a-shared-base.md)
  (the towers and what each holds),
  [ADR-0027](../docs/adr/0027-the-monitor-tower-owns-the-interpreter-floor.md)
  (the floor, the guard and the help text),
  [ADR-0001](../docs/adr/0001-hand-rolled-perfetto-protobuf-encoder.md)
  (`perfetto` stays out of the monitoring runtime; ADR-0027 narrows that
  argument to the pyperf hook),
  [ADR-0023](../docs/adr/0023-the-pyperf-hook-annotates-and-does-not-drive.md)
  (the hook runs inside the target, which is why it is monitor-tower code)

## 1. Problem statement

gcmon will not install unless the machine runs Python 3.15, and 3.15 is in
beta. Half of what gcmon does needs nothing from it. `gcmon combine` reads a
capture and writes a trace; it touches no process and no interpreter
internals, and it is unavailable to anyone whose machine is a release behind.

That is not a hypothetical operator. The pipeline that publishes gcmon's own
benchmark results runs 3.13, on a scientific stack that has no 3.15 wheels,
and it cannot install gcmon at all. Specs 0061, 0062 and 0063 add three more
commands with the same shape, so the number of things gcmon can do only on a
beta interpreter is about to triple.

The reason is one import. `monitoring/events_reader.py` and
`monitoring/monitor.py` take what they need from `_remote_debugging`, and
`requires-python` was set to match. It is per-distribution metadata, so it
speaks for every command in the package, including the ones that read a file
and stop.

Underneath that, nothing separates the two kinds of command. `cli` may import
every layer, so a command that only reads a tracefile may reach into the
monitoring layer, and the layer test will pass.

## 2. Solution

gcmon installs and runs on Python 3.13. `combine` works there, and so will
`report` and `compare` when they land.

`gcmon --help` prints the same text on every interpreter. `monitor` and `run`
are listed, with `(requires Python 3.15+)` in their descriptions. On 3.13,
running one prints what it needs and which interpreter it found, and exits
non-zero:

```
gcmon: monitor requires Python 3.15 or newer; this interpreter is 3.13.1
```

On 3.15 nothing an operator does changes.

## 3. User stories

1. As someone handed a tracefile, I want to install gcmon on the interpreter I
   already have, so that reading a file does not cost me an interpreter
   upgrade.
2. As the maintainer of the results pipeline, I want to install gcmon on 3.13,
   so that it can call gcmon's reader instead of keeping its own queries
   against gcmon's track layout.
3. As an operator on 3.13 who types `gcmon monitor`, I want to be told that my
   interpreter is too old, so that I do not conclude my install is broken.
4. As an operator on 3.15, I want every command to behave exactly as it did,
   so that this costs me nothing.
5. As someone reading `docs/cli.md`, I want the documented help text to be the
   help text on my machine, whichever interpreter I run.
6. As a maintainer adding an offline command, I want the layer test to fail
   when I import the monitoring layer from it, so that the boundary holds
   without my remembering it.
7. As a maintainer, I want the base and the analysis tower checked on the
   floor by CI, so that a 3.15-only construct fails on the commit that writes
   it rather than on an operator's machine.

## 4. Implementation decisions

**What moves.** `exporters/combine.py` and `exporters/jsonl_io.py` become
`analysis/combine.py` and `analysis/jsonl_io.py`;
`cli/commands/convert_cmd.py` becomes `cli/analyze/convert_cmd.py`.
`monitor_cmd`, `run_cmd`, `monitoring_options` and `cli/_env.py` become
`cli/monitor/`. `parser_factory` becomes `cli/shared/parser_factory.py`, which
both towers may import and which imports nothing.

`monitoring_base.py` goes to `cli/monitor/loop_runner.py`. It holds
`run_monitoring_loop`, and its old name meant "shared by the monitoring
commands", which now collides with the base the two towers stand on.

`_env` moves whole. Every one of its getters has one caller,
`monitoring_options`, and the variables it names are `monitor`'s and `run`'s.

`jsonl_io` moves whole. `JsonlExporter` serializes through
`model.protocol.to_mapping` and calls nothing in it; `write_jsonl`'s only
caller is `combine_files`. Nothing in the monitor tower reads or writes a
capture file after the fact.

**The layer table** gains the towers, and `layer_of` answers by subdirectory:

```python
"analysis":    frozenset({"model", "exporters", "support"}),
"cli.shared":  frozenset(),
"cli.monitor": frozenset({"model", "exporters", "stats", "control",
                          "monitoring", "support", "cli.shared"}),
"cli.analyze": frozenset({"model", "exporters", "stats", "analysis",
                          "support", "cli.shared"}),
"cli":         frozenset({...every layer, the three above included...}),
FOLDED = {"pyperf": "cli.monitor"}
```

`analysis` is denied `stats`. `combine` and `jsonl_io` read and write files
and compute nothing, and spec 0061's fold from records into a `StreamingStats`
sits in `cli.analyze`, which has it.

`cli.shared` takes nothing and is taken by both towers, so no tower imports
`cli`, where `main.py` reaches both. `ROOT_CLI` is unchanged and stays `cli`:
`__init__.py` and `__main__.py` belong to neither tower. `layer_of` tries the
two-segment name before the head, so `cli.monitor.run_cmd` answers
`cli.monitor` and `cli.main` answers `cli`.

`FOLDED` stops parking a question and answers one, because `pyperf/hook.py`
imports `control` and runs inside the target. It requires nothing of 3.15, and
a tower is not defined by that (ADR-0026).

**A parser separates from its handler.** `monitor_cmd` and `run_cmd` import
`monitoring.target_process` and `monitoring.wait_policy` beside their
`add_parser`, so registering a subcommand currently drags in the tower that
serves it. The `add_parser` half moves to a module that imports only
`monitoring_options`, `parser_factory` and the base; the handler keeps the
rest. `monitoring_options` already has this shape, reaching no further than
`_env`, `model.schedule`, `stats.views` and `support.time_units`, and is the
model for the split.

**One function decides what the guard does.** `cli/main.py` attempts the
monitor tower's handlers and passes the outcome to a single registration
function, which either wires the real handler or wires one that prints the
requirement and returns non-zero. Both branches are then reachable on any
interpreter, and the parser is built from the same `add_parser` either way,
making the help text identical rather than merely similar.

**The guard classifies the failure it caught.** An `ImportError` below 3.15
registers the stub. On 3.15 and above it propagates: there the tower is
present, the fault is a circular import, a renamed symbol or a half-built
install, and the message in section 2 would blame the interpreter while
printing a version that meets the requirement. Rejected: catching
`ImportError` and stubbing whatever raised it.

Rejected: registering the subcommands only when the import succeeds. It makes
the help text a property of the machine, so `docs/cli.md` can be true on one
interpreter or the other, and argparse answers the missing subcommand with
`invalid choice`, which reads as a broken install.

**`pyproject.toml`.** The floor is `python = ">=3.13"` under
`[tool.poetry.dependencies]`, which is where poetry states it. The classifiers
gain `Programming Language :: Python :: 3.13` and `:: 3.14` beside the 3.15
already there. No extra: `analysis` and the `perfetto` it holds arrive in spec
0061, with the reader that imports them.

Rejected: extras named for the towers, `monitor` and `analyze`, defined as
unions of the capability extras. Both unions would contain `ddsketch`, which
belongs to the base and to neither tower, and a union has to be kept in step
with its members by hand.

**Two sets of re-exports go.** `gcmon.__init__` drops `EventsMonitor`,
`ChildProcess` and `ChildProcessRunner`, because importing the package has to
work on the floor. `gcmon.exporters.__init__` drops `combine_files` and
`convert_jsonl_to_trace_format`, which moved. Every `__init__.py` stays eager;
nothing here defers an import of gcmon's own code.

Nothing shims either set. A module-level `__getattr__` is a deferred import of
gcmon's own code, and re-exporting `EventsMonitor` is what the floor forbids.
The five names and the two import paths `gcmon.exporters.combine` and
`gcmon.exporters.jsonl_io` go under `### Removed`; the floor and the guard go
under `### Changed`; the move is internal. The release is 0.7.0.

**The test tree splits before the floor job can run.** `tests/conftest.py`
imports `EventsMonitor`, `ExternalProcess` and `no_wait_policy` at module
scope, and a root conftest is imported for every run under `tests/`, so on the
floor nothing collects. `tests/helpers.py` imports `events_reader`, `monitor`
and `process_registry`, and `tests/exporters/test_combine.py`,
`test_jsonl_io.py` and `test_jsonl_exporter.py` all import it: the files the
floor job exists to run. `tests/exporters/loss_row.py` imports `EventsMonitor`
too.

The monitor-tower fixtures move down to `tests/monitoring/conftest.py`, and
`helpers.py` splits into a tower-free half and a monitor-side one. A marker
cannot do this work, because pytest imports a module to read its markers. Only
path selection skips a file without importing it.

**CI gains a floor job** on the floor interpreter, doing three things. It runs
the base and analysis suites, selected by path with `--ignore` for the monitor
directories. It runs `mypy --python-version 3.13` over `model`, `support`,
`stats`, `exporters`, `analysis` and `cli.shared`, which reaches the stdlib
names an unexecuted line uses and the suite cannot. It runs `gcmon --help` and
asserts the exit code and that `monitor` and `run` are listed. The monitor
tower's suite runs where it always did.

**The documentation the floor changes.** The README badge reads `3.15+`, and
two sentences say 3.15 is required. They become two claims where there was
one: gcmon installs and `combine` runs on 3.13, and monitoring wants 3.15 on
both sides ([ADR-0020](../docs/adr/0020-attach-to-a-process-once.md)).
`docs/cli.md`'s `monitor` and `run` sections quote the new help text.

## 5. Seams and testing decisions

- **Seam:** `cli.main.main`, called with an argument vector, for everything an
  operator sees: the help text, the exit code, the message. The layer table's
  own test for the boundary.
- **New seam needed:** none, but the fixtures move first. `main` is the seam
  the CLI tests use and `test_layering.py` already walks the imports; neither
  runs on the floor until `tests/conftest.py` and `tests/helpers.py` stop
  importing the monitor tower.
- **What makes a good test here:** the help text asserted as text, and the
  guard asserted through what `main` returns and prints rather than through
  the import that produced it. A test that patches `sys.modules` to hide
  `_remote_debugging` is testing Python, not gcmon.
- **Prior art:** `tests/architecture/test_layering.py` for the boundary, and
  the existing CLI tests for `main`.
- **Cases:**
  1. The registration function, given an unavailable monitor tower, produces a
     parser whose help text equals the one it produces given an available
     tower.
  2. That same parser, asked to run `monitor`, returns non-zero and names both
     the requirement and the running interpreter's version.
  3. `combine` round-trips a capture with no monitor tower available.
  4. An import from `analysis` into `monitoring`, from `cli.analyze` into
     `control`, or from either tower into `cli`, fails the layer test.
  5. Regression: on 3.15 the full suite passes unchanged. Case 1 is what holds
     the two help texts equal. No test can read what the other CI job printed,
     and a checked-in golden would compare terminal widths as much as parsers.

## 6. Out of scope

- **The tracefile reader.** Spec 0061. This spec creates `analysis/` and adds
  nothing that imports `perfetto`.
- **The `analysis` extra.** Spec 0061 declares it beside the reader that
  imports it. Declaring it here ships a release whose extra installs a wheel
  nothing calls.
- **Workload sanitizers and `compare`.** Specs 0062 and 0063.
- **The results pipeline's own change.** Deleting its queries and depending on
  gcmon is work in that repository, tracked there. This spec only makes the
  dependency installable.
- **Emitting tabular files.** gcmon hands back rows; whatever writes CSV keeps
  writing it. Revisit if a consumer needs a shape rows cannot carry.
- **Two distributions.** Rejected in
  [ADR-0026](../docs/adr/0026-two-towers-over-a-shared-base.md); the towers
  are what would make it mechanical if the question returns.
- **Moving `stats` into the analysis tower.** The live table and the offline
  one are one accumulation, and spec 0061 depends on their staying so.

## 7. Further notes

- Whether the lower seam takes a path or an open trace processor is 0061's
  decision, not this one. A consumer running several queries over one file
  should not reopen it once per query.
