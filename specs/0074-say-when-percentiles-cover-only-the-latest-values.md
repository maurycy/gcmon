# 0074: A table whose percentiles cover only the latest values says so

- **Status:** Not started
- **Kind:** bug (reporting)
- **Effort:** XS
- **Origin:** issue #154, landed as #222, and a design session on 2026-10-18
  on whether to label the windowed percentiles or remove them
- **Respects:**
  - [ADR-0016](../docs/adr/0016-the-ring-is-the-statistics-unit.md): every
    printed row covers one ring over one unbroken stretch. Amended when this
    lands: the consequence bullet limiting "`Count`, `Sum` and percentiles
    describe the same records" to installs with `ddsketch` gains that, without
    it, a note under the table says so.
  - [ADR-0001](../docs/adr/0001-hand-rolled-perfetto-protobuf-encoder.md):
    `ddsketch` stays an optional dependency that degrades gracefully. This
    states the degradation in the output and keeps it.

## 1. Problem

A developer installs gcmon with `pip install gcmon`, without the `[stats]`
extra, and profiles a script under `gcmon run --stats=full`. Its gen-0 ring
collects 4096 times, long pauses first and short ones at the end. The ring's
`GC Pause(0)` row prints an `Avg` of `0.762` beside a `P99` of `0.050`, and
the `Total` row above it prints the same pair. An average above every
percentile reads as a gcmon bug. Nothing in the output says the percentiles
cover only the row's latest 1024 values, while `Count`, `Sum` and `Avg` cover
all of them.

## 2. Evidence

`Stats` keeps two summaries of the values a row takes: `_data`, a
`deque(maxlen=MAX_BUFFER_LEN)`, and `_sketch`, a `DDSketch` over every value,
which is `None` when `HAS_DDSKETCH` is false. `Stats._quantiles` reads the
sketch once the buffer is full and the buffer otherwise, so without the sketch
every percentile is a quantile of the latest `MAX_BUFFER_LEN` values. `count`,
`sum` and `average` are running totals over all of them.

Reproduction, deterministic on any machine:

```python
with patch("gcmon.stats.stats.HAS_DDSKETCH", False):
    s = Stats()
for _ in range(3 * Stats.MAX_BUFFER_LEN):
    s.update(1_000_000)
for _ in range(Stats.MAX_BUFFER_LEN):
    s.update(50_000)
s.average()       # 762500.0
s.percentile(99)  # 50000.0
```

`_print_footer` prints a note for each thing the cells cannot say: coverage,
lifetime totals, rings with no row. None of them covers this.
`docs/statistics.md` does, under "Without `[stats]` extra" ("a long session
loses its early shape"), which a reader of a pasted table never sees.

## 3. Scope

**Affected:** the `--stats` table of `gcmon monitor` and `gcmon run`, under
both views and every `--table-format`, on every platform, on an install
without `ddsketch`. A row is affected once it has taken more than
`MAX_BUFFER_LEN` values: the `Total` and ring rows of every phase, and
`Read Time`, which takes one value per poll.

**Not affected:**

- **An install with the `[stats]` extra.** Its percentiles cover every value,
  settled rings included since #222.
- **`Count`, `Sum`, `Avg`, `Cov` and `F`.** Running values, independent of the
  buffer.
- **The trace and the capture.** No percentile reaches either.
- **The pyperf hook.** It holds no statistics.

**Why the suite does not catch it:** the windowed numbers are intended, and
`TestARingThatOutgrewItsBuffer::test_without_ddsketch_they_describe_the_records_the_buffer_kept`
asserts them. What is missing is output, and no case in
`tests/stats/test_stats_output.py` prints a table from a `Stats` past the
buffer without a sketch.

## 4. Proposed change

1. **`Stats` answers whether its percentiles cover every value it took.** The
   answer is no only with no sketch and more than `MAX_BUFFER_LEN` values. It
   survives `materialize`, which drops the sketch: a settled ring that read
   its percentiles from the sketch still covers every value, and must not read
   as windowed afterwards.
2. **`print_stats` collects the answer from the rows it builds** and passes it
   to `_print_footer`. Walking the view's rows a second time in the footer
   would leave two places deciding which rows a view prints. `Total` takes
   every record a ring takes, so checking `Total` and `Read Time` alone gives
   the same answer today; the change does not rest on that.
3. **`_print_footer` prints the note right after the coverage note**, with the
   limit read from `Stats.MAX_BUFFER_LEN`:

   ```
   Percentiles cover at most a row's latest 1024 values. Install gcmon[stats] for percentiles over every value.
   ```

   It states the rule, the limit and the fix, and no count or list of rows: a
   reader tells an affected row by its sampled count, the first number in
   `Count`. It sits beside the coverage note because both qualify the same
   columns.
4. **`docs/statistics.md`.** "The notes under the table" gains the entry after
   **1. Coverage.**, and the entries after it renumber. "Without `[stats]`
   extra" says the note appears.
5. **ADR-0016.** Amend the consequence bullet as `Respects` says.

## 5. Seams and testing decisions

- **Seam:** `print_stats` through `capsys` in
  `tests/stats/test_stats_output.py`. The printed note is what the operator
  reads, and this is the highest seam that sees it.
- **New seam needed:** none. `HAS_DDSKETCH` is patched on `gcmon.stats.stats`
  before the `StreamingStats` is built, as `TestARingThatOutgrewItsBuffer`
  does.
- **What makes a good test here:** assert the note and its place among the
  notes in the printed footer. The predicate alone passes with a footer that
  never reads it.
- **Prior art:** `TestTheNoteOnRingsWithNoRow`,
  `TestTheFooterNotesAreNumbered`, and
  `TestTheTwoViews::test_the_untracked_note_is_full_only`.
- **Cases:**
  1. Without `ddsketch`, a run whose `Total` pause row passes `MAX_BUFFER_LEN`
     values prints the note, under `--stats=total` and `--stats=full`. Fails
     today.
  2. Without `ddsketch`, a run whose only row past the buffer is `Read Time`
     prints it.
  3. On a lossy run it prints right after the coverage note; on a lossless run
     it is note 1.
  4. With `ddsketch`, the same run prints no note, whether its ring is still
     running or settled.
  5. Regression guard: without `ddsketch`, a run whose rows all stay within
     the buffer prints the footer it prints today.

## 6. Out of scope

- **Making `ddsketch` required, or gcmon computing whole-run percentiles
  itself** with a log-bucketed histogram. Either removes the windowed mode,
  and the extra stays optional.
- **A marker on each windowed cell**, as `~` marks an estimate. On a long run
  it lands on most percentile cells to say what one note says once.
- **A logged warning.** It scrolls away and never travels with a pasted table.
- **A count or a list of the affected rows in the note.** The sampled count on
  each row already says which.
- **A glossary entry for "value".** The note's context makes the word plain.
- **`MAX_BUFFER_LEN`.** Raising it moves the window, and the note prints
  whatever it is.
