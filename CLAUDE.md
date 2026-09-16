# CLAUDE.md

Orientation for agents. README.md is for users; this file is the stuff that is expensive to
rediscover. Read this, then grep. Do not read `autotester.py` end to end (1875 lines).

## What it does

Runs a console program against the `Example execution N` transcripts written in its own
docstring or header comment, then classifies each failure ("number formatting", "off by
one", "crash") instead of only diffing it. Python, C, C++, Java, JavaScript, Rust, Ruby.

## Verify every change with one command

```bash
python3 selftest.py
```

Covers the line classifier, transcript extraction from every comment style, all three
sample folders across seven languages, and the VS Code extension (needs `node`). It prints
`ALL OK` or a list of `BAD` lines and exits non-zero. Missing compilers are skipped, not
failed. There is no other test suite. Run it before claiming anything works.

To inspect behaviour programmatically, use `--json` rather than parsing the terminal
report. `--no-color` when capturing terminal output.

## Layout

`autotester.py` is the entire tool, one file, no dependencies. Jump by section marker,
each unique and greppable:

| `# ---- <name>` | holds |
| --- | --- |
| `languages` | `Language` dataclass, `LANGUAGES` registry, `lang_for` |
| `parsing` | comment extraction, `parse_examples`, `parse_actual` |
| `running` | `build_program`, `run_python`, `run_terminal` (pty), `run_pipes` |
| `diagnosis` | `KINDS`, `line_kinds`, `number_kind`, `diagnose`, `hint_for`, `file_summary` |
| `reading the source` | `Source`, per-language scanners, `demote_extras`, `source_hint` |
| `testing a file` | `test_file`, the per-file entry point |
| `report (terminal)` | `report_file` |
| `report (editors and tools)` | `problem_lines`, `file_json` |
| `VS Code (no extension needed)` | `setup_vscode`, writes tasks.json |
| `project settings` | `autotester.json` discovery |

Flow: `test_file` → `find_transcript` → `parse_examples` → `build_program` → `run_example`
per example → `diagnose` → `file_summary` → one of four report surfaces.

`selftest.py` holds the expectations as plain dicts near the top: `EXPECT`, `EXPECT_LANG`,
`EXPECT_COLON`, `LINE_CASES`, `COMMENT_CASES`. Add to those when you add behaviour.

`samples/` programs are **deliberately buggy**. Each one's comment states the diagnosis it
must produce. Never "fix" a sample; fix the tester or change the expectation.

## Invariants that break silently

- **Line counts never change during extraction.** `dedent_lines` and `strip_javadoc` return
  the same number of lines they were given, because `Example.at[]` maps each transcript
  line to a file line for editor squiggles. Off-by-one here misplaces every diagnostic.
- **`strip_javadoc` must decline on a box of stars.** `****` is content, ` * ` is a prefix.
  The rule: strip only if every non-blank line matches `^\s*\*(?!\*)`.
- **`demote_extras` must not count reads.** A read inside a loop answers many input lines,
  so counts prove nothing. It demotes only when a candidate's prompt matches no read prompt
  *and* the whole line is exactly what one print statement emits.
- **`prompts_match` needs the shorter string to be ≥ 2/3 of the longer.** Plain `endswith`
  makes "Distance" match "Enter the distance" and wrecks input detection.
- **`SENTINEL` framing is shared.** The Python `WRAPPER` and the pty runner both emit
  `prompt + SENTINEL + value + "\n"`; `parse_actual` is the only consumer. Keep them aligned.
- **`KINDS` insertion order is tie-break priority**, most specific first (`kind_counts`).
- **`source_hint` returns `(text, replaces)`.** `True` substitutes the generic hint, `False`
  appends `(line N prints it)` to it. Returning a bare string breaks `hint_for`.
- **The extension mirrors constants.** `extension.js` duplicates the header regex (as
  `HEADER`), the language list (`LANGS`, `GLOB`) and `STRUCTURAL`, marked `Keep in sync`.
  Changing the registry means editing both plus `activationEvents` in `package.json`.

## The pty runner, in short

Everything except Python runs on a pseudo-terminal, because C only flushes a newline-less
`printf("Enter x: ")` when stdout is a tty. Terminal **echo is turned off** and the runner
injects the sentinel itself, so the output has the same shape as the Python wrapper's. A
value is typed as soon as the program's last line matches the example's prompt, falling
back to a quiet timer (`--quiet`, default 0.2s). Correct programs finish in ~0.1s.

- `Language.echoes=True` (Node only) means the runtime prints typed input itself. Then the
  runner injects nothing and `reinsert_echo` marks the positions afterwards. Node also
  emits ANSI cursor codes; `ANSI_RE` strips them from all pty output.
- Node needs the pty. With pipes its prompts concatenate onto one line.
- The EOF marker is deleted from the transcript on timeout, or a stuck loop is reported as
  "wanted more input".

## Things that already cost someone an hour

- **Integer divide-by-zero does not trap on ARM macOS.** It returns 0. A C crash sample must
  dereference a null pointer instead. `samples/other-languages/crash.c` does.
- **Rust `print!` and Ruby `print` do not flush** without a newline. The samples call
  `io::stdout().flush()` / set `$stdout.sync = true`, as real interactive programs do.
- **Windows is untested.** `run_pipes` is the fallback when `HAVE_PTY` is false; C prompts
  may land late there without `fflush`.
- The tester skips its own folder by location, not by name, so `samples/` never shows up in
  a student's scan. Explicitly naming a path inside the folder still tests it.

## Adding things

**A language:** append to `LANGUAGES`; add a branch in `analyze_source`; add a spec regex if
its format syntax is not printf-style; add `CALLS` and any `LANG_HINTS` overrides; add
`format_fix`; add a sample plus an `EXPECT_LANG` entry and a `TOOLS` entry in `selftest.py`;
update `LANGS`/`GLOB` in `extension.js` and `activationEvents` in `package.json`.

**A failure kind:** add to `KINDS` at the right priority, detect it in `line_kinds` or
`number_kind`, add a `LINE_CASES` row, and add a sample if it is worth demonstrating.

## Scope

The repo root is this folder. Its parent holds the user's coursework and is not part of the
project. Never widen the git repo to the parent, and never commit anything from it.

Extension changes need a rebuild to take effect:
`python3 vscode-extension/build_vsix.py --install`, then Developer: Reload Window. The
`.vsix` is gitignored.
