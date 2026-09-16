# ADR-0012: Support Perfetto output in `combine`, and dual output only in live mode

- **Status:** Superseded by [ADR-0021](0021-write-one-trace-format.md)
- **Date:** 2026-06-25

> gcmon writes one trace format now, and `chrome+perfetto` went with the
> second one. [ADR-0021](0021-write-one-trace-format.md) states the half of
> this record that survives, and holds the reasoning with it:
> `combine --output-format perfetto`, the normalization split, Perfetto not
> being an input, and `-o` used verbatim.
