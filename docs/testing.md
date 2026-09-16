# Testing gcmon

How the suites are split, how to run each one, and the conventions a test in
them keeps. [`CONTRIBUTING.md`](../CONTRIBUTING.md) covers setting up a
working copy; [ADR-0014](adr/0014-perfetto-integration-test-strategy.md) holds
the reasoning behind the split.

## The default suite

```bash
poetry run just test
```

Trace-processor tests sit in it, behind no marker and with no `importorskip`.
The `perfetto` package is a dev-group dependency, so a developer running
`pytest` has it, and the tests import it at module level. The first run
downloads the trace-processor binary and later runs read the cache.

Coverage has a floor of 80%, set by `fail_under` in `pyproject.toml`.

## The deselected suites

`addopts` in `pyproject.toml` carries
`-m 'not stress and not benchmark and not fuzz and not architecture'`, so a
passing `pytest` covers less than it looks.

| Marker | Command | CI job | What it covers |
|---|---|---|---|
| `stress` | `just stress` | `stress-test` | thread safety of the exporter and control-client pipelines |
| `fuzz` | `just fuzz` | `fuzz-test` | randomized differential tests against the real trace processor |
| `architecture` | `just architecture` | `architecture` | the code's structure, read without running it |
| `benchmark` | `just bench` | CodSpeed workflow | performance benchmarks |

`just stress` runs two passes: `-k "control" --count 40` and
`-m stress --count 20`. The repetition is what gives a probabilistic test its
chance to fail.

`just fuzz` passes no `--count`. The seeds are fixed, so repeating a trial
re-runs the same trace; widen coverage by raising the trial count in the test.
The marker is there for cost, since the trace processor starts once per trial.

The `stress-test` and `fuzz-test` jobs are skipped on `main` and on
`release/*`.

## Writing a stress test

- Release the threads with `threading.Barrier`, never `time.sleep`.
- Use `join(timeout=...)` as a watchdog only.
- Capture each worker's exceptions into a list and assert it empty after the
  join. No worker asserts on shared state.
- The contract is no deadlock and no uncaught exception. The operating system
  decides the interleaving, so a test does not assert on it.

## Where each kind of test lives

| Directory | What it holds |
|---|---|
| `tests/exporters/` | the encoder, the Perfetto format, the track state, and the trace-processor suites |
| `tests/monitoring/` | the monitor, its loop, the reader and the samplers |
| `tests/cli/` | the parsers and each subcommand end to end |
| `tests/model/` | the record structs, the loss arithmetic, the schedule |
| `tests/stats/` | the `--stats` views, the table and the per-ring arithmetic |
| `tests/analysis/` | `combine` and the JSONL round trips |
| `tests/control/` | the control plane, client and server |
| `tests/architecture/` | the layering and lock-order checks |
| `tests/benchmarks/` | the CodSpeed benchmarks |
| `tests/support/`, `tests/infra/`, `tests/pyperf/` | the shared helpers, the repo scripts, and the pyperf hook |

Two helpers are worth knowing before writing a Perfetto test.
`tests/helpers.py` holds the reader every trace-processor test goes through,
and `tests/exporters/test_perfetto_exporter_integration.py` holds the
trace-processor fixture and the trace-writing helper. The oracle that compares
a `.pftrace` against the events it was built from lives in
`tests/cli/analyze/test_convert_cmd_perfetto.py`.
