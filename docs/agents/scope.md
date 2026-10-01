# Scope of a request

A request covers what it names, and nothing adjacent.

## Finish one thing, then ask

The second issue found mid-task waits. Finish the named work, run the checks,
report it. Then list the neighbours, one line each, with what changing each
would cost. `Should X go too?` is one line; finding an unasked-for edit costs
a re-read of the whole diff.

This holds in both directions. Something missing next to the named work was
usually dropped on purpose. Restoring it is the same error as removing an
extra.

## What counts as adjacent

- The caller of the function named, and its tests.
- A neighbouring rule in the same config block or stylesheet.
- Formatting, wrapping and import order in a file opened for one edit.
- A stale comment next to the line changed.

## Exceptions

These edits ride along without asking:

- What the named change breaks. A rename that leaves a caller unresolved is
  not finished at the rename. Neither is one that leaves the old spelling in a
  doc or inside a string literal, SQL included.
- What a checked-in tool rewrites: `wrap_markdown.py` on a file already
  edited, the formatter on a file already touched.
