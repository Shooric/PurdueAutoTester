# PurdueAutoTester

Test a console program against the example runs written in its own comments.

You already write the sample runs your assignment asks for. autotester runs the program,
types the inputs from those examples, compares what came out, and tells you **what kind of
mistake** it was: wrong wording, a missing decimal place, integer division, an off-by-one,
a crash. One file, no dependencies, and it works the same for Python, C, C++, Java,
JavaScript, Rust and Ruby.

```
$ python3 autotester.py InLab02.c

== InLab02.c   [C]
   FAIL  Example 1   [230, 78.65, 5 11, 165, 4]
      why:  number formatting (1 line)
      hint: line 74 prints %.1f, but the example shows 2 decimal places: use %.2f
      line 9 (number formatting):
      want: The price of the textbook is $78.65
      got:  The price of the textbook is $78.7
   0/1 passed
```

## Quick start

```bash
python3 autotester.py hw3.py          # one file
python3 autotester.py labs/           # every program in a folder
python3 autotester.py                 # pick files with a dialog
```

Handy alias, in your `~/.zshrc` (use the real path to this file):

```bash
alias pytest-cs='python3 ~/path/to/autotester/autotester.py'
```

## Writing the examples

Put them in the module docstring (Python) or in a comment (everything else). A line with
an arrow is something the user types: the text before the arrow is the prompt, the text
after it is what gets typed. Every other line is expected output.

```python
"""
Example execution 1:
Enter the first number: -> 3
Enter the second number: -> 4
The average is 3.50
"""
```

The same thing in C, in a `/* */` or `//` comment:

```c
/*
Example execution 1:
Enter the first number: -> 3
Enter the second number: -> 4
The average is 3.50
*/
```

Blank lines are ignored, and so are differences in runs of spaces and in curly quotes,
unless you pass `--strict`. Number the examples however you like; `-e 2` runs just one.

### If your class writes `Prompt: value` instead of an arrow

Plenty of courses show the typed value straight after the prompt, with no arrow:

```
Enter the price of the textbook: 78.65
The price of the textbook is $78.65
```

Test those with `--input-marker ': '`. The obvious problem is that `: ` also shows up in
ordinary output, so a line like `Speed: 25.00` looks exactly like input. autotester reads
your source to tell them apart: a line only counts as input if the program really reads
after printing that prompt, and if the whole line is not something one print statement
produces by itself. `--no-source` turns that off.

One prompt can answer several values. `Enter base and height: 5 11` is a single typed line
feeding one `scanf("%f %f", &base, &height)`.

### Settings for a whole folder

Drop an `autotester.json` next to your programs, or in any folder above them, so you never
type the flags again. Anything on the command line still wins.

```json
{
  "input_marker": ": ",
  "timeout": 10
}
```

Keys: `input_marker`, `timeout`, `strict`, `keep_blank`, `ignore`, `lang`, `quiet`,
`python`, `no_pty`, `no_source`, `unified`, `context`, `examples`. `--no-config` ignores it.

## Using it in VS Code

Two ways. Option A takes one command and installs nothing. Option B is nicer to use.

### Option A: a build task (nothing to install)

1. Open your project folder in VS Code.
2. Open a terminal there and run, with the real path to this file:

   ```bash
   python3 ~/path/to/autotester/autotester.py --vscode
   ```

   That writes `.vscode/tasks.json` in the folder you are in.
3. Open one of your programs and press **Ctrl+Shift+B** (**Cmd+Shift+B** on a Mac).

The report appears in the terminal, and every mismatch is also listed in the **Problems**
panel at the bottom. Click one to jump to that line of the example, or to the line of the
program that crashed. There is a second task, *Autotester: test whole folder*, under
**Terminal > Run Task...**.

### Option B: the extension

1. Run this once, with no Node.js or npm needed:

   ```bash
   python3 ~/path/to/autotester/vscode-extension/build_vsix.py --install
   ```

   If it says the `code` command was not found, open VS Code, press
   **Ctrl/Cmd+Shift+P**, run **Shell Command: Install 'code' command in PATH**, and try
   again. You can also build it without installing (drop the `--install`) and then use
   **Extensions panel > the `...` menu > Install from VSIX...** and pick the `.vsix` file
   it made.
2. In VS Code run **Ctrl/Cmd+Shift+P > Developer: Reload Window**.
3. Open a program that has `Example execution` blocks.

You now get:

* a **run button in the gutter** next to every `Example execution N` line,
* the whole file and workspace in the **Test Explorer** (the beaker icon in the sidebar),
* a **diff view** when you click a failure, with the diagnosis and the hint,
* **squiggles** under the lines that did not match, plus compiler errors and warnings,
* the command **Autotester: Test Current File** in the play-button menu, top right.

Settings live under **Ctrl/Cmd+, > Extensions > Autotester**:

| Setting                  | What it does                                                        |
| ------------------------ | ------------------------------------------------------------------- |
| `autotester.script`      | Path to `autotester.py`. Empty uses the copy bundled in the extension. |
| `autotester.python`      | Which Python to run. Empty follows the Python extension's choice.    |
| `autotester.inputMarker` | Set it to `: ` for `Prompt: value` transcripts.                      |
| `autotester.args`        | Extra flags, e.g. `["--strict"]`.                                    |

An `autotester.json` beside your programs beats these settings, and is the easier way to
set a marker for a whole class folder.

The extension bundles a copy of `autotester.py`. If you edit the script, either rebuild
(`python3 vscode-extension/build_vsix.py --install`) or point `autotester.script` at the
file you are editing.

## Languages

The language comes from the file suffix; `--lang` overrides it.

| Language   | Suffixes        | Needs installed | Examples live in                      |
| ---------- | --------------- | --------------- | ------------------------------------- |
| Python     | `.py`           | nothing         | the module docstring, or `#` comments |
| C          | `.c`            | `cc`            | `/* */` or `//` comments              |
| C++        | `.cpp .cc .cxx` | `c++`           | `/* */` or `//` comments              |
| Java       | `.java`         | `javac` `java`  | `/* */` or `//` comments              |
| JavaScript | `.js .mjs`      | `node`          | `/* */` or `//` comments              |
| Rust       | `.rs`           | `rustc`         | `/* */` or `//` comments              |
| Ruby       | `.rb`           | `ruby`          | `#` comments                          |

Compiled languages are built once per file into a temporary folder, with `-Wall` where the
compiler supports it, and the compiler's own errors and warnings are reported with their
line numbers. Javadoc-style `*` prefixes are stripped from comments, while a box drawn out
of `*` characters is left alone.

Everything except Python runs on a real pseudo-terminal, which matters more than it sounds:
a C program's `printf("Enter x: ")` only reaches the screen at the right moment when
stdout is a terminal. Each value is typed the instant the program asks for it, so the
transcript lines up with what a person sitting at the keyboard would see.

One caveat for **Rust and Ruby**: `print!` and `print` do not flush on their own, so a
prompt with no newline can arrive late. Real interactive programs in those languages call
`io::stdout().flush()` or set `$stdout.sync = true`, and the samples here do.

## Reading a failure

Every failing example gets a `why:` line and a `hint:`. When one kind of mistake explains
most of a file's failures, the summary says `Consistent issue: ...` once instead of
repeating it, so a single fix is easy to spot. Hints are written for the language you are
using, and name the exact source line when the source makes that clear.

| `why` says                          | it means                                                                |
| ----------------------------------- | ----------------------------------------------------------------------- |
| number formatting                   | right value, wrong decimals or separators (`3.5` for `3.50`)             |
| rounding                            | off in the last decimal place (`2.66` for `2.67`)                        |
| integer division                    | a whole number where a decimal was expected                              |
| decimal instead of whole number     | `3.5` where `3` was expected                                             |
| off by one                          | differs by exactly 1: loop bounds, or where a counter starts             |
| sign flipped                        | `-5` for `5`                                                             |
| factor of 100                       | `0.125` for `12.5`: a percentage conversion                              |
| numbers swapped                     | the right numbers in the wrong order                                     |
| wrong value                         | the calculation gives a different number                                 |
| letter case / spacing / punctuation | same words, different capitalization, spaces or punctuation              |
| wording                             | the text is different                                                    |
| missing line / extra line           | fewer or more lines than the example                                     |
| crash                               | an exception or a fatal signal, with the line and a hint for common ones |
| timeout                             | never finished: an infinite loop, or waiting for input                   |
| input mismatch                      | the program reads more or fewer inputs than the example provides         |

A program that will not compile is reported as a build failure with the compiler's own
messages, the same way a Python syntax error is.

## All the options

```
-e, --examples N [N ...]   only run these example numbers
-v, --verbose              show full expected/actual output and stderr
-t, --timeout SEC          seconds per example (default 5)
-u, --unified              a classic unified diff instead of want/got lines
-c, --context N            diff context lines with --unified (default 2)
    --strict               exact matching: no prompt/dash/quote/whitespace tidying
    --keep-blank           compare blank lines too
    --ignore REGEX         skip example lines matching REGEX (repeatable)
    --input-marker REGEX   what marks typed input (default: an arrow such as "-> ")
    --lang NAME            force a language instead of using the file suffix
    --python PATH          interpreter used for Python programs
    --quiet SEC            how long to wait for a prompt before typing (default 0.2)
    --no-source            do not read the source for sharper hints and input detection
    --no-pty               do not use a pseudo-terminal for non-Python programs
    --no-config            ignore any autotester.json
    --json                 results as JSON, for editors and scripts
    --problems             also print "file:line:col: severity: message" lines
    --vscode [FOLDER]      write the VS Code build task described above
    --no-color
```

## What is in this folder

```
autotester.py          the whole tester; copy it anywhere on its own if you like
README.md              this file
selftest.py            checks every sample and the extension
samples/
  python/              one tiny Python program per kind of mistake
  other-languages/     the same bugs in C, C++, Java, JavaScript, Rust and Ruby
  colon-style/         "Prompt: value" transcripts, with an autotester.json
vscode-extension/      the extension, its packager, and its tests
```

The sample programs are **meant to fail**; that is what they demonstrate. Folder scans
skip this folder automatically, so they never turn up in your own results. To watch them
run:

```bash
python3 autotester.py samples/other-languages
```

## Checking that it all still works

```bash
python3 selftest.py
```

It covers the line-by-line classifier, transcript extraction from every comment style, all
three sample folders, and the VS Code extension. Samples whose compiler is not installed
are skipped rather than failed.

## For other editors and tools

`--json` prints one document: per file the `language`, compiler `diagnostics` and
`warnings`, an `examples` list (each with `expected`, `actual`, `inputs`, `reason`,
`detail`, `hint`, and one `issues` entry per mismatched line carrying its 1-based `line`
in the file) and a `summary` naming the dominant kind of mistake. `--problems` prints
`file:line:col: severity: message` lines that any editor's error parser understands. The
VS Code extension is a 200-line consumer of exactly that JSON.
