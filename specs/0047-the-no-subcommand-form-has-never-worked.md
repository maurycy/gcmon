# 0047: Require a subcommand

- **Status:** In progress. The parser and the dead branches landed in #146;
  the nine documented examples still print the form gcmon rejects
- **Kind:** bug (reporting)
- **Effort:** XS
- **Origin:** spec 0045 section 7, 2026-08-17, which fixed the two documented
  examples it had to touch and deliberately left the question open
- **Respects:** none

## 1. Problem

`README.md` opens its Quick Start with `gcmon 12345`, and `docs/cli.md` says
that `gcmon` without a subcommand monitors. gcmon requires one, so the
operator's first command, copied from the top of the README, exits 2 with
`argument command: invalid choice: '12345'`.

## 2. Evidence

`gcmon.cli.main._create_parser` passes `required=True` to `add_subparsers`,
and `gcmon.cli.main.main` dispatches through `args.func` alone. `gcmon` with
no subcommand prints a usage line naming the three choices, and `gcmon 12345`
the invalid-choice message; both exit 2.
`tests/test_cli.py::test_main_no_subcommand_exits_2` and
`::test_main_invalid_subcommand_exits_2` hold that.

Nine documented examples still print the rejected form: `README.md` Quick
Start (two), `docs/cli.md` under "What you'll see" (one) and "monitor" (four),
and `docs/rss.md` (two). "monitor" prints `gcmon 12345` and
`gcmon monitor 12345` on consecutive lines, one of which runs.

## 3. Scope

**Affected:** those nine examples, and the sentence "Without one it monitors"
that opens `docs/cli.md`.

**Not affected:** `gcmon.cli.main`, which landed. `gcmon monitor <pid>`,
`gcmon run`, `gcmon combine` and `gcmon --version` behave as their own
examples show.

**Why the suite didn't catch it:** no test runs a command line the
documentation prints. The CLI tests assert the exit status of an argv the test
itself spells.

## 4. Proposed change

The documentation stops offering a form gcmon rejects.

Rewrite the nine examples to name `monitor`, and delete "Without one it
monitors" from `docs/cli.md`. The `gcmon 12345` and `gcmon monitor 12345` pair
under "monitor" collapses to the second line.

**Rejected: make the bare form work.** `main` would detect a leading token
that is not a subcommand choice, an all-digit pid, and insert `monitor` before
it. It costs a parser that guesses at its first argument, and it buys a
shortcut for one subcommand out of three.
[ADR-0018](../docs/adr/0018-stats-requires-a-view-and-keeps-no-bare-alias.md)
is the precedent: `--stats` lost its bare spelling rather than gaining an
alias, so that the source and the docs carry one spelling each. **What would
reopen it:** an operator asking for the shortcut who is not reading this repo.

**Rejected: print help and exit 0 on a bare `gcmon`.** Friendlier, but it
needs an explicit branch, which is the shape of the code #146 deleted, and it
answers a bare `gcmon` differently from `gcmon 12345`. Exit 2 with the usage
line keeps one answer to "you did not name a subcommand".

**No alias, unlike [0050](0050-name-the-poll-interval-for-what-it-is.md).**
That spec keeps `--rate` working because command lines in the wild carry it.
This form has never worked, so there is nothing in the wild to keep.

## 5. Seams and testing decisions

The behaviour is settled and covered. `tests/test_cli.py` runs `main` with an
argv list for both rejected spellings, for the three subcommands, and for
`--version`, which is where the dispatch decision can be observed.

What remains is documentation and adds no test: each rewritten line names a
subcommand, which is read rather than asserted.

## 6. Out of scope

- **`--rate` in `docs/cli.md`.** One of the rewritten examples carries it.
  This spec puts `monitor` in front of it and leaves the option name to
  [0050](0050-name-the-poll-interval-for-what-it-is.md).
- **A test that runs the documented command lines.** It is the check that
  would have caught this, and it is a suite of its own: extracting every
  fenced `bash` block from `README.md` and `docs/`, and deciding which of them
  may execute.
- **A deprecation cycle for the bare form.** There is nothing to deprecate: no
  release has ever accepted it, and 0.7.0 shipped the requirement.
- **`--stats` and its two views.** Spec 0045 landed those and rewrote the two
  examples that carried a bare `--stats` into the subcommand form on the way
  past. The rest of the no-subcommand examples were left as they are, which is
  why this spec exists.

## 7. Further notes

The `CHANGELOG.md` entry landed with #146 and shipped in 0.7.0 under bug
fixes. The documentation sweep corrects pages that already exist, so it joins
the standing `### Internal` line rather than taking an entry.

The ADR is still unwritten. Shaped like ADR-0018, it holds the two rejections
in section 4, so that the next person to propose a shortcut form finds the
reasoning rather than the `add_subparsers` call.
