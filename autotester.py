#!/usr/bin/env python3
"""

##################################################################
Fast ZSH Alias: 
alias pytest-cs='python3 /full/path/to/autotester/autotester.py'
##################################################################

Actually using this: 
* Put that alias in your ~/.zshrc with the real path to this file, then open a new terminal.
* Then just run the command: pytest-cs path/to/file.py or pytest-cs path/to/folder/ to test every program in a folder.

Program relies on the "Example execution N" transcripts found in a program's docstring or header comment. It runs the program in a separate process, replacing input() with a version that echoes the typed value and a newline, just like a real terminal. The captured transcript is then compared with the docstring.

tldr: all you need is a doc string with example executions and this program will test your code against those examples(obv case sensitive).

Not a terminal person?  Two options, both in VS Code:
* python3 autotester.py --vscode   (run once inside your project folder) writes
  .vscode/tasks.json, so Ctrl+Shift+B (Cmd+Shift+B on Mac) tests the file you have
  open and every mismatch shows up in the Problems panel; clicking one jumps to that
  line of the docstring example.
* vscode-extension/ next to this file is a small VS Code extension: run buttons next
  to every "Example execution N", results in the Test Explorer, squiggles under the
  lines that don't match.  Install it with
      python3 vscode-extension/build_vsix.py --install
  See README.md in this folder for both options, step by step.

######################################################################

example_tester.py - run the "Example execution N" transcripts found in a
program's docstring against that program, and diff the results.

In the docstring, a line containing "-> " (also "->>> ", "--> ") is user
input: the text before the arrow is the prompt, the text after it is what gets
typed. Every other line is expected program output.

Usage:
    python example_tester.py                     # pick file(s) with a dialog
    python example_tester.py hw3.py              # test one file
    python example_tester.py hw3.py hw4.py       # several files
    python example_tester.py projects/           # every program (with examples) under a folder
    python example_tester.py hw3.py -e 1 4       # only examples 1 and 4
    python example_tester.py hw3.py -v           # also print full expected/actual output
    python example_tester.py hw3.py --strict     # exact matching (prompts, dashes, spaces)
    python example_tester.py lab2.c --input-marker ': '   # "Prompt: value" transcripts
    python example_tester.py hw3.py --json       # results as JSON (for editors, plugins, scripts)
    python example_tester.py hw3.py --problems   # also print "file:line: message" lines for editors
    python example_tester.py --vscode            # set up the VS Code task described above

Languages: Python, C, C++, Java, JavaScript, Rust and Ruby, picked from the file
suffix (--lang overrides it). Python transcripts live in the module docstring;
everywhere else they live in a comment - a /* ... */ block (javadoc stars and
boxes of stars are both handled) or a run of // or # lines. Compiled languages
are built once per file, and the compiler's own errors and warnings are
reported with their line numbers. Anything other than Python runs on a real
pseudo-terminal, so prompts appear exactly where a terminal would show them.

Other transcript styles: --input-marker takes a regex, so a class that writes
"Enter the price: 78.65" instead of an arrow is tested with --input-marker ': '.
A marker like that also turns up in ordinary output, so autotester reads the
program's source to tell the two apart: a line is only input if the program
really reads after printing that prompt. Put settings that every file in a
folder needs in an autotester.json beside them, e.g.

    {"input_marker": ": ", "timeout": 10}

Reading a failure: every failing example gets a "why:" line naming the kind of
mistake - wording, letter case, spacing, punctuation, number formatting,
rounding, integer division, off by one, sign, wrong value, missing/extra line,
crash, timeout or input mismatch - and a hint for it. Each block of the diff is
tagged the same way. Hints are written in the language being tested, and where
the source makes it clear they name the exact line to change, for example
"line 22 prints %.1f, but the example shows 2 decimal places: use %.2f". When
one kind of mistake explains most of the failures in a file, the summary calls
it out as a "Consistent issue", so a single fix (say, printing with two
decimals) can be spotted without reading every diff.

How it works: the program runs in a separate process where input() is replaced
by a version that echoes the typed value and a newline, just like a real
terminal. The captured transcript is then compared with the docstring.
"""
import argparse
import ast
import difflib
import inspect
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from collections import Counter
from dataclasses import dataclass, field
from itertools import zip_longest
from pathlib import Path

try:                                  # not on Windows
    import fcntl, pty, select, termios
    HAVE_PTY = True
except ImportError:
    HAVE_PTY = False

SENTINEL = "\x1e<<INPUT>>\x1e"   # marks where input() was called in the captured output
EOF_MARK = "\x00EOF"

HEADER_RE = re.compile(r"^[ \t]*Example[ \t]+execution[ \t]*#?[ \t]*(\d+)\b.*$", re.I | re.M)
INPUT_RE = re.compile(r"[ \t]*-+>+ ?")          # "-> ", "->>> ", "--> "
NUM_RE = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|-?\.\d+")   # 42  -3.5  1,000.25  .5
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]|\x07")   # colors and cursor moves
TRACE_RE = re.compile(r'^\s*File "(.+?)", line (\d+)', re.M)
DEFAULT_IGNORE = [r"^\s*What the user types"]   # instruction notes, not program output
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", ".idea", ".vscode"}

DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")
QUOTES = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x00A0: " "}

# Runs inside the child process.
WRAPPER = r'''
import builtins, os, runpy, sys
SENT = %r
EOF_MARK = %r
target = sys.argv[1]

def _input(prompt=""):
    sys.stdout.write(str(prompt))
    line = sys.stdin.readline()
    if not line:
        sys.stdout.write(SENT + EOF_MARK + "\n")
        sys.stdout.flush()
        raise EOFError("program asked for more input than the example provides")
    line = line.rstrip("\r\n")
    sys.stdout.write(SENT + line + "\n")
    sys.stdout.flush()
    return line

builtins.input = _input
sys.argv = [target]
sys.path.insert(0, os.path.dirname(os.path.abspath(target)))
runpy.run_path(target, run_name="__main__")
''' % (SENTINEL, EOF_MARK)


# ----------------------------------------------------------------- languages
@dataclass
class Language:
    name: str
    suffixes: tuple
    comments: str                 # where transcripts live: "docstring", "c-like" (/* */ and //) or "hash" (#)
    build: tuple = ()             # argv template run once per file; {src} {exe} {dir} {stem}
    run: tuple = ()               # argv template for each example
    needs: tuple = ()             # executables that must be installed
    runner: str = "pty"           # "python" uses the input() wrapper above; "pty" drives a terminal
    echoes: bool = False          # the runtime prints typed input itself (node's readline does)


LANGUAGES = [
    Language("Python", (".py",), "docstring", runner="python"),
    Language("C", (".c",), "c-like", build=("cc", "-Wall", "-o", "{exe}", "{src}", "-lm"),
             run=("{exe}",), needs=("cc",)),
    Language("C++", (".cpp", ".cc", ".cxx", ".c++"), "c-like",
             build=("c++", "-Wall", "-o", "{exe}", "{src}"), run=("{exe}",), needs=("c++",)),
    Language("Java", (".java",), "c-like", build=("javac", "-d", "{dir}", "{src}"),
             run=("java", "-cp", "{dir}", "{stem}"), needs=("javac", "java")),
    Language("JavaScript", (".js", ".mjs"), "c-like", run=("node", "{src}"), needs=("node",), echoes=True),
    Language("Rust", (".rs",), "c-like", build=("rustc", "-o", "{exe}", "{src}"), run=("{exe}",), needs=("rustc",)),
    Language("Ruby", (".rb",), "hash", run=("ruby", "{src}"), needs=("ruby",)),
]
BY_SUFFIX = {sfx: L for L in LANGUAGES for sfx in L.suffixes}
BY_NAME = {L.name.lower(): L for L in LANGUAGES}
SUFFIXES = tuple(BY_SUFFIX)

# file:line:col: severity: message   (clang, gcc, javac with -Xdiags, rustc's --> lines)
DIAG_RE = re.compile(r"^(?P<file>[^\s:][^:]*):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
                     r"(?P<sev>error|warning|note|fatal error):\s*(?P<msg>.*)$", re.M)
JAVAC_RE = re.compile(r"^(?P<file>[^\s:][^:]*\.java):(?P<line>\d+):\s*(?P<sev>error|warning):\s*(?P<msg>.*)$", re.M)


def lang_for(path, override=None):
    if override:
        L = BY_NAME.get(override.lower())
        if not L:
            raise ValueError(f"unknown language {override!r}; try one of: "
                             + ", ".join(sorted(BY_NAME)))
        return L
    return BY_SUFFIX.get(Path(path).suffix.lower())


def missing_tools(lang):
    return [t for t in lang.needs if not shutil.which(t)]


# ----------------------------------------------------------------- helpers
class C:
    on = False
    @classmethod
    def w(cls, code, s):
        return f"\033[{code}m{s}\033[0m" if cls.on else s

def green(s): return C.w("32", s)
def red(s): return C.w("31", s)
def yellow(s): return C.w("33", s)
def cyan(s): return C.w("36", s)
def bold(s): return C.w("1", s)
def dim(s): return C.w("2", s)


def norm_text(s, opts):
    s = s.rstrip("\r").rstrip()
    if not opts.strict:
        s = s.translate(DASHES).translate(QUOTES)
        s = re.sub(r"[ \t]+", " ", s)
    return s


def render_input(prompt, value, opts):
    """Canonical text for a line where the user typed something."""
    value = value.rstrip()
    if opts.strict:
        prompt = prompt.rstrip()              # keep ':' and every other character as is
    else:
        prompt = re.sub(r"[\s:>\-]+$", "", norm_text(prompt, opts))  # drop trailing ':', '->', spaces
        value = norm_text(value, opts)
    return f"{prompt} -> {value}" if prompt else f"-> {value}"


# ----------------------------------------------------------------- parsing
@dataclass
class Example:
    number: int
    inputs: list
    expected: list
    line: int = 0                                  # file line of the "Example execution N" header
    at: list = field(default_factory=list)         # file line of each expected line
    prompts: list = field(default_factory=list)    # text before the marker on each input line


def dedent_lines(lines):
    """textwrap.dedent for a list of lines: never changes how many there are."""
    indents = [len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()]
    n = min(indents) if indents else 0
    return [ln[n:] if ln.strip() else "" for ln in lines]


JAVADOC_RE = re.compile(r"^\s*\*(?!\*)")


def strip_javadoc(lines):
    """Drop the leading '*' of a /** ... */ comment, but never the '*' of a box of stars.

    A line of '****' has a second star right after the first, so a transcript that draws a
    box is left alone; a real javadoc block (every line a lone star) is stripped."""
    body = [ln for ln in lines if ln.strip()]
    if len(body) < 2 or not all(JAVADOC_RE.match(ln) for ln in body):
        return lines
    return [re.sub(r"^(\s*)\*[ \t]?", r"\1", ln) if ln.strip() else ln for ln in lines]


def c_like_blocks(src):
    """Yield (lines, first file line) for every /*...*/ block and every run of // lines.

    Skips string and character literals, so a "/*" inside a printf is not a comment."""
    lines = src.split("\n")
    line_of = lambda i: src.count("\n", 0, i)          # 0-based
    i, n = 0, len(src)
    run = None                                          # a run of consecutive // lines
    while i < n:
        c = src[i]
        if c in "\"'":                                  # a string or char literal
            q, i = c, i + 1
            while i < n and src[i] != q:
                i += 2 if src[i] == "\\" else 1
            i += 1
        elif src.startswith("/*", i):
            if run:
                yield run[0], run[1] + 1
                run = None
            end = src.find("*/", i + 2)
            end = n if end < 0 else end
            first, last = line_of(i), line_of(end)
            chunk = lines[first:last + 1][:]            # blank out the /* and */, keep every column
            sc = i - (src.rfind("\n", 0, i) + 1)
            chunk[0] = " " * (sc + 2) + chunk[0][sc + 2:]
            if end < n:
                ec = end - (src.rfind("\n", 0, end) + 1)
                chunk[-1] = chunk[-1][:ec] + " " * 2 + chunk[-1][ec + 2:]
            yield chunk, first + 1
            i = end + 2
        elif src.startswith("//", i):
            ln = line_of(i)
            end = src.find("\n", i)
            end = n if end < 0 else end
            text = re.sub(r"^(\s*)//+[ \t]?", r"\1", lines[ln])
            if run and run[1] + len(run[0]) == ln:
                run[0].append(text)
            else:
                if run:
                    yield run[0], run[1] + 1
                run = [[text], ln]
            i = end + 1
        else:
            i += 1
    if run:
        yield run[0], run[1] + 1


def hash_blocks(src):
    """Yield (lines, first file line) for every run of '#' comment lines."""
    run = None
    for ln, raw in enumerate(src.split("\n")):
        if re.match(r"^\s*#", raw) and not raw.lstrip().startswith("#!"):
            text = re.sub(r"^(\s*)#+[ \t]?", r"\1", raw)
            if run and run[1] + len(run[0]) == ln:
                run[0].append(text)
            else:
                if run:
                    yield run[0], run[1] + 1
                run = [[text], ln]
        elif run:
            yield run[0], run[1] + 1
            run = None
    if run:
        yield run[0], run[1] + 1


def find_in_comments(src, blocks):
    for lines, start in blocks(src):
        clean = dedent_lines(strip_javadoc(lines))     # strip first: "* Example execution 1" must match
        if any(HEADER_RE.search(ln) for ln in clean):
            return "\n".join(clean), start
    return None, None


def find_docstring(path, src=None):
    """Return (cleaned docstring, file line of its first line), or (None, None)."""
    src = path.read_text(encoding="utf-8") if src is None else src
    tree = ast.parse(src, filename=str(path))
    nodes = [tree.body[0].value] if tree.body and isinstance(tree.body[0], ast.Expr) else []
    nodes += list(ast.walk(tree))             # fall back to any string containing examples
    for node in nodes:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and HEADER_RE.search(node.value):
            raw = node.value.split("\n")
            lead = next((i for i, ln in enumerate(raw) if ln.strip()), 0)   # blank lines cleandoc drops
            return inspect.cleandoc(node.value), node.lineno + lead
    if HEADER_RE.search(src):                 # examples in # comments rather than a docstring
        return find_in_comments(src, hash_blocks)
    return None, None


def find_transcript(path, lang=None):
    """Return (transcript text, file line of its first line) for any supported language."""
    lang = lang or lang_for(path)
    if lang is None:
        return None, None
    src = path.read_text(encoding="utf-8")
    if lang.comments == "docstring":
        return find_docstring(path, src)
    return find_in_comments(src, c_like_blocks if lang.comments == "c-like" else hash_blocks)


def parse_examples(doc, opts, start=1, source=None):
    ignore = [re.compile(p) for p in DEFAULT_IGNORE + opts.ignore]
    custom = bool(getattr(opts, "input_marker", None))
    marker = re.compile(opts.input_marker) if custom else INPUT_RE
    headers = list(HEADER_RE.finditer(doc))
    examples = []
    for i, h in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(doc)
        hline = start + doc.count("\n", 0, h.start())
        rows = []
        for j, raw in enumerate(doc[h.end():end].split("\n")):
            if j == 0:                                   # tail of the header line itself
                continue
            if any(r.search(raw) for r in ignore):
                continue
            if not raw.strip() and not opts.keep_blank:
                continue
            rows.append((hline + j, raw, marker.search(raw)))
        cands = [dict(row=k, line=raw, prompt=raw[:m.start()], value=raw[m.end():].rstrip())
                 for k, (_, raw, m) in enumerate(rows) if m]
        # only a marker the user chose can collide with ordinary output; an arrow does not
        drop = {cands[d]["row"] for d in demote_extras(cands, source)} if (custom and source) else set()
        inputs, lines, at, prompts = [], [], [], []
        for k, (fline, raw, m) in enumerate(rows):
            if m and k not in drop:
                value = raw[m.end():].rstrip()
                inputs.append(value)
                prompts.append(raw[:m.start()])
                lines.append(render_input(raw[:m.start()], value, opts))
            else:
                lines.append(norm_text(raw, opts))
            at.append(fline)
        while opts.keep_blank and lines and lines[-1] == "":
            lines.pop()
            at.pop()
        examples.append(Example(int(h.group(1)), inputs, lines, hline, at, prompts))
    return examples


def parse_actual(stdout, opts):
    parts = stdout.replace("\r\n", "\n").split("\n")   # not splitlines(): it splits on \x1e
    if parts and parts[-1] == "":
        parts.pop()
    lines, used, ran_out = [], 0, False
    for raw in parts:
        if SENTINEL in raw:
            prompt, _, value = raw.partition(SENTINEL)
            if value == EOF_MARK:
                ran_out = True
                lines.append(norm_text(prompt, opts) + "   <-- program wanted more input here")
                continue
            used += 1
            lines.append(render_input(prompt, value, opts))
        else:
            if not raw.strip() and not opts.keep_blank:
                continue
            lines.append(norm_text(raw, opts))
    while opts.keep_blank and lines and lines[-1] == "":
        lines.pop()
    return lines, used, ran_out


# ----------------------------------------------------------------- running
@dataclass
class Result:
    example: Example
    passed: bool
    actual: list
    used: int            # how many of the example's inputs the program read
    ran_out: bool        # the program asked for more input than the example has
    stderr: str
    code: object         # exit code; None when timed out
    timed_out: bool
    reason: str = ""     # primary kind from KINDS ("" when passed)
    detail: str = ""     # the text after "why:"
    hint: str = ""
    where: int = 0       # program line of a crash, when known
    issues: list = field(default_factory=list)   # one dict per mismatched line, or one structural issue
    blocks: list = field(default_factory=list)   # diff blocks: (expected index, [(want, got, kinds), ...])


@dataclass
class Program:
    """One compiled/interpreted program, ready to run an example against."""
    path: Path
    lang: Language = None
    argv: list = None
    cwd: str = ""
    tmp: str = ""
    error: str = ""                                # build or setup failure
    diags: list = field(default_factory=list)      # (file, line, col, severity, message)
    warnings: list = field(default_factory=list)   # the same, from a build that succeeded


def parse_diags(text, path):
    """Compiler messages as (file, line, col, severity, message)."""
    out = []
    for m in list(DIAG_RE.finditer(text)) + list(JAVAC_RE.finditer(text)):
        d = m.groupdict()
        f = d["file"]
        if Path(f).name != path.name:              # only this program's own messages
            continue
        out.append((str(path), int(d["line"]), int(d.get("col") or 1),
                    "error" if "error" in d["sev"] else d["sev"], d["msg"].strip()))
    seen, uniq = set(), []
    for d in out:
        if d[:4] + (d[4],) not in seen:
            seen.add(d[:4] + (d[4],))
            uniq.append(d)
    return uniq


def build_program(path, opts):
    """Compile the program once, if its language needs it."""
    path = Path(path).resolve()
    prog = Program(path, cwd=str(path.parent))
    try:
        prog.lang = lang_for(path, opts.lang)
    except ValueError as e:
        prog.error = str(e)
        return prog
    if prog.lang is None:
        prog.error = (f"no language for {path.suffix or path.name!r}; supported: "
                      + ", ".join(sorted(SUFFIXES)) + " (or pass --lang)")
        return prog
    miss = missing_tools(prog.lang)
    if miss:
        prog.error = f"{prog.lang.name} needs {' and '.join(miss)}, which is not installed"
        return prog
    if prog.lang.runner == "python":
        prog.argv = [opts.python, "-c", WRAPPER, str(path)]
        return prog
    sub = dict(src=str(path), stem=path.stem, python=opts.python)
    if prog.lang.build:
        prog.tmp = tempfile.mkdtemp(prefix="autotester-")
        sub.update(dir=prog.tmp, exe=str(Path(prog.tmp) / path.stem))
        cmd = [a.format(**sub) for a in prog.lang.build]
        try:
            b = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=max(60.0, opts.timeout), cwd=prog.cwd)
        except (subprocess.TimeoutExpired, OSError) as e:
            prog.error = f"could not build: {e}"
            return prog
        text = b.stderr + b.stdout
        found = parse_diags(text, path)
        if b.returncode != 0:
            prog.error = f"{prog.lang.name} build failed ({shlex.join(cmd)})"
            prog.diags = found or [(str(path), 1, 1, "error", text.strip().splitlines()[0]
                                    if text.strip() else f"exit code {b.returncode}")]
            return prog
        prog.warnings = [d for d in found if d[3] == "warning"]
    prog.argv = [a.format(**sub) for a in prog.lang.run]
    return prog


def run_python(prog, ex, opts):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    stdin = "".join(v + "\n" for v in ex.inputs)
    try:
        p = subprocess.run(prog.argv, input=stdin, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=opts.timeout, cwd=prog.cwd, env=env)
        return p.stdout, p.stderr, p.returncode, False
    except subprocess.TimeoutExpired as e:
        dec = lambda b: b.decode("utf-8", "replace") if isinstance(b, bytes) else (b or "")
        return dec(e.stdout), dec(e.stderr), None, True


def prompt_tail(s):
    """The last line of S, normalized the way a prompt is, for anchoring."""
    return re.sub(r"[\s:>\-]+$", "", re.sub(r"[ \t]+", " ", s.split("\n")[-1])).strip()


def run_terminal(prog, ex, opts):
    """Run the program on a pseudo-terminal, typing each input when it is asked for.

    Terminal echo is turned off and the typed text is inserted into the transcript
    ourselves, so the captured output has the same sentinels as the Python wrapper.
    An input is sent as soon as the program's last line matches the example's prompt,
    and otherwise once the program has been quiet for --quiet seconds."""
    master, slave = pty.openpty()
    try:
        a = termios.tcgetattr(slave)
        a[3] &= ~(termios.ECHO | termios.ECHOE | termios.ECHOK | termios.ECHONL | termios.ECHOCTL)
        termios.tcsetattr(slave, termios.TCSANOW, a)
    except termios.error:
        pass
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", TERM="dumb")
    try:
        p = subprocess.Popen(prog.argv, stdin=slave, stdout=slave, stderr=subprocess.PIPE,
                             cwd=prog.cwd, env=env, close_fds=True, start_new_session=True)
    except OSError as e:
        os.close(master); os.close(slave)
        return "", f"could not run {prog.argv[0]}: {e}", None, False
    os.close(slave)
    os.set_blocking(p.stderr.fileno(), False)
    out, err, since, used, ran_out, sent_eof, timed_out = [], [], "", 0, False, False, False
    echoes, eof_at = prog.lang.echoes, None
    pending = list(ex.inputs)
    start = last = time.monotonic()
    quiet, grace = opts.quiet, max(opts.quiet * 4, 0.8)
    while True:
        if time.monotonic() - start > opts.timeout:
            timed_out = True
            break
        try:
            ready, _, _ = select.select([master, p.stderr], [], [], 0.02)
        except (OSError, ValueError):
            break
        if p.stderr in ready:
            try:
                chunk = p.stderr.read() or b""
            except (OSError, ValueError):
                chunk = b""
            if chunk:
                err.append(chunk.decode("utf-8", "replace"))
        if master in ready:
            try:
                data = os.read(master, 65536)
            except OSError:
                data = b""
            if data:
                t = ANSI_RE.sub("", data.decode("utf-8", "replace"))
                out.append(t)
                since += t
                last = time.monotonic()
                continue
            break                                   # the child closed the terminal
        alive = p.poll() is None
        idle = time.monotonic() - last
        seen = any(c.strip() for c in out)
        if pending:
            want = prompt_tail(ex.prompts[used]) if used < len(ex.prompts) else ""
            if (want and prompt_tail(since).endswith(want)) or \
                    (idle > quiet and (seen or time.monotonic() - start > grace)):
                value = pending.pop(0)
                try:
                    os.write(master, (value + "\n").encode("utf-8"))
                except OSError:
                    break
                if not echoes:                      # otherwise the program prints it for us
                    out.append(SENTINEL + value + "\n")
                used += 1
                since = ""
                last = time.monotonic()
                continue
        elif alive and not sent_eof and idle > max(quiet * 3, 0.4):
            sent_eof = ran_out = True               # still running with nothing left to type
            eof_at = len(out)
            out.append(SENTINEL + EOF_MARK + "\n")
            try:
                os.write(master, b"\x04")
            except OSError:
                break
            last = time.monotonic()
            continue
        if not alive and master not in ready:
            break
    if timed_out or p.poll() is None:
        try:
            os.killpg(os.getpgid(p.pid), 9)
        except (OSError, ProcessLookupError):
            p.kill()
    try:
        os.close(master)
    except OSError:
        pass
    try:
        p.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        rest = p.stderr.read()
        if rest:
            err.append(rest.decode("utf-8", "replace"))
        p.stderr.close()
    except (OSError, ValueError):
        pass
    if timed_out and eof_at is not None:
        del out[eof_at]                             # a stuck program was never waiting for input
    text = "".join(out)
    if echoes:
        text = reinsert_echo(text, ex.inputs)
    return text, "".join(err), (None if timed_out else p.returncode), timed_out


def reinsert_echo(text, values):
    """Mark where input was typed in a transcript the runtime echoed itself."""
    out, vi = [], 0
    for raw in text.replace("\r\n", "\n").split("\n"):
        ln = raw.rstrip("\r")
        if SENTINEL not in ln and vi < len(values) and values[vi] and ln.endswith(values[vi]):
            out.append(ln[:-len(values[vi])] + SENTINEL + values[vi])
            vi += 1
        else:
            out.append(ln)
    return "\n".join(out)


def run_pipes(prog, ex, opts):
    """Fallback for systems without a pty (Windows): same pacing, over plain pipes.

    A program that does not flush its prompts (C without fflush) may show them late."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    try:
        p = subprocess.Popen(prog.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=prog.cwd, env=env, bufsize=0)
    except OSError as e:
        return "", f"could not run {prog.argv[0]}: {e}", None, False
    out, used = [], 0
    try:
        stdin = "".join(v + "\n" for v in ex.inputs)
        so, se = p.communicate(stdin.encode("utf-8"), timeout=opts.timeout)
        used = len(ex.inputs)
        text = so.decode("utf-8", "replace")
        lines = text.split("\n")                    # put the typed values back where a terminal shows them
        rebuilt, vi = [], 0
        for ln in lines:
            if vi < len(ex.inputs) and ex.prompts and vi < len(ex.prompts) \
                    and prompt_tail(ex.prompts[vi]) and prompt_tail(ln).endswith(prompt_tail(ex.prompts[vi])):
                rebuilt.append(ln + SENTINEL + ex.inputs[vi])
                vi += 1
            else:
                rebuilt.append(ln)
        return "\n".join(rebuilt), se.decode("utf-8", "replace"), p.returncode, False
    except subprocess.TimeoutExpired:
        p.kill()
        so, se = p.communicate()
        return so.decode("utf-8", "replace"), se.decode("utf-8", "replace"), None, True


def run_example(prog, ex, opts):
    if prog.lang.runner == "python":
        stdout, stderr, code, timed_out = run_python(prog, ex, opts)
    elif HAVE_PTY and not opts.no_pty:
        stdout, stderr, code, timed_out = run_terminal(prog, ex, opts)
    else:
        stdout, stderr, code, timed_out = run_pipes(prog, ex, opts)
    actual, used, ran_out = parse_actual(stdout, opts)
    passed = (not timed_out and actual == ex.expected and used == len(ex.inputs))
    return Result(ex, passed, actual, used, ran_out, stderr, code, timed_out)


# ----------------------------------------------------------------- diagnosis
# kind: (label, hint).  Ordered from most to least specific: a tie in the counts goes to the earlier kind.
KINDS = {
    "int-division": ("integer division",
                     "a whole number where a decimal was expected: look for //, int() or round() where / is needed"),
    "float-division": ("decimal instead of whole number",
                       "a decimal where a whole number was expected: use // or int()"),
    "off-by-one": ("off by one", "differs by exactly 1: check the range() bounds, or where a counter starts"),
    "sign": ("sign flipped", "the sign is flipped: check the order of a subtraction"),
    "percent": ("factor of 100", "off by a factor of 100: check the percentage conversion (x * 100 or x / 100)"),
    "number-order": ("numbers swapped", "the right numbers in the wrong order: check the order of the values in print()"),
    "rounding": ("rounding",
                 "off in the last decimal place: f\"{x:.2f}\" rounds when printing, int() truncates; round only at the end"),
    "number-format": ("number formatting", "right value, wrong format: match the example's decimal places and separators"),
    "wrong-value": ("wrong value", "the calculation gives a different number: redo the formula by hand with these inputs"),
    "case": ("letter case", "same words, different capitalization: match the example exactly"),
    "spacing": ("spacing", "same text, different spaces: check the spaces around punctuation and between words"),
    "punctuation": ("punctuation", "same words, different punctuation: check periods, colons, commas, $ and %"),
    "wording": ("wording", "the text differs: copy the exact wording from the example"),
    "missing": ("missing line", "the program never printed this line: check the if/loop that should print it"),
    "extra": ("extra line", "the program printed a line the example doesn't have: look for a stray print() or one loop pass too many"),
    "crash": ("crash", "the program raised an exception: read the error message and line number below"),
    "timeout": ("timeout", "the program never finished: look for an infinite loop, or an input() the example doesn't answer"),
    "input": ("input mismatch",
              "the program reads a different number of inputs than the example: check the count and order of the input() calls"),
}
PRIORITY = list(KINDS)
STRUCTURAL = {"crash", "timeout", "input"}      # one issue per example instead of one per line

def signal_name(n):
    try:
        import signal as _sig
        return _sig.Signals(n).name
    except (ImportError, ValueError):
        return f"signal {n}"


CRASH_HINTS = [   # (regex on the exception line, hint)
    (r"SIGSEGV|SIGBUS",
     "a bad pointer or index: in C check that every scanf argument has an & in front of it, "
     "and that array indexes stay in range"),
    (r"SIGFPE", "divided by zero: check for a 0 input, or a count/total that is still 0"),
    (r"SIGABRT", "the program aborted itself: a failed assert, or memory freed twice"),
    (r"ZeroDivisionError", "dividing by zero: check for a 0 input, or a count/total that is still 0"),
    (r"ValueError: (invalid literal|could not convert)",
     "int()/float() got text it can't convert: check which input is converted, and the order of the input() calls"),
    (r"UnboundLocalError", "a variable is used inside a function before it is assigned there"),
    (r"NameError", "a name is misspelled, or used before it is assigned"),
    (r"TypeError: .*(str|int|float)", "mixing text and numbers: convert the input with int() or float(), or the number with str()"),
    (r"TypeError", "a value has the wrong type: check what each variable holds at that line"),
    (r"IndexError", "an index is past the end of the list or string: check the range() bounds"),
    (r"KeyError", "the dictionary has no such key: check the spelling, or use .get()"),
    (r"RecursionError", "the function calls itself forever: check the base case"),
    (r"AttributeError", "no such method or attribute: check the spelling, and the type of the value"),
    (r"ModuleNotFoundError|ImportError", "an import failed: check the module name, or that the imported file sits in the same folder"),
]


def split_numbers(s):
    """(numbers in the line, the line with every number replaced by '#')."""
    return NUM_RE.findall(s), NUM_RE.sub("#", s)


def num_val(s):
    return float(s.replace(",", ""))


def num_decimals(s):
    return len(s.rsplit(".", 1)[1]) if "." in s else 0


def text_kind(a, b):
    """How two number-free texts differ, from the mildest difference up."""
    a, b = a.lower(), b.lower()
    if a == b:
        return "case"
    a, b = re.sub(r"\s+", "", a), re.sub(r"\s+", "", b)
    if a == b:
        return "spacing"
    a, b = re.sub(r"[^\w#]", "", a), re.sub(r"[^\w#]", "", b)
    if a == b:
        return "punctuation"
    return "wording"


def number_kind(w, g):
    """How a printed number (g) differs from the expected one (w)."""
    wv, gv, wd, gd = num_val(w), num_val(g), num_decimals(w), num_decimals(g)
    if wv == gv:
        return "number-format"
    if gd > wd and round(gv, wd) == wv:                       # too many decimals
        return "number-format"
    if 0 < gd < wd and round(wv, gd) == gv:                   # too few decimals
        return "number-format"
    if wd and abs(wv - gv) <= 10 ** -wd * 1.001:
        return "rounding"
    if wd and not gd and abs(wv - gv) < 1:                   # 2.5 printed as 2 (or 3)
        return "int-division"
    if not wd and gd and abs(wv - gv) < 1:                   # 3 printed as 3.5
        return "float-division"
    if abs(abs(wv - gv) - 1) < 1e-9:
        return "off-by-one"
    if wv == -gv:
        return "sign"
    if wv and gv and (abs(wv / gv - 100) < 1e-6 or abs(gv / wv - 100) < 1e-6):
        return "percent"
    return "wrong-value"


def line_kinds(want, got):
    """Every way an expected line differs from what the program printed (number kinds first)."""
    if got is None:
        return ["missing"]
    if want is None:
        return ["extra"]
    if want == got:
        return []
    wn, wt = split_numbers(want)
    gn, gt = split_numbers(got)
    kinds = []
    if wn != gn:
        if len(wn) == len(gn):
            wv, gv = [num_val(x) for x in wn], [num_val(x) for x in gn]
            if wv != gv and sorted(wv) == sorted(gv):
                kinds.append("number-order")
            else:
                kinds += [number_kind(w, g) for w, g in zip(wn, gn) if w != g]
        else:
            kinds.append("wording")      # a different count of numbers reads as a text difference
    if wt != gt:
        kinds.append(text_kind(wt, gt))
    return list(dict.fromkeys(kinds)) or ["wording"]


def diff_blocks(expected, actual):
    """[(expected index, [(want, got, kinds), ...]), ...] for every differing region."""
    sm = difflib.SequenceMatcher(None, expected, actual, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        pairs = [(w, g, line_kinds(w, g)) for w, g in zip_longest(expected[i1:i2], actual[j1:j2])]
        blocks.append((i1, pairs))
    return blocks


def crash_info(path, stderr):
    """(exception line, line number inside the program) from a traceback, else (None, None)."""
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    if not lines or "Traceback" not in stderr:
        return None, None
    where = None
    for m in TRACE_RE.finditer(stderr):
        if Path(m.group(1)).name == path.name:
            where = int(m.group(2))
    return lines[-1], where


def kind_counts(issues):
    """[(kind, number of issues showing that kind)], most common first."""
    c = Counter(k for i in issues for k in i["kinds"])
    return sorted(c.items(), key=lambda kv: (-kv[1], PRIORITY.index(kv[0])))


CALLS = {                       # (how this language reads input, how it prints)
    "Python": ("input()", "print()"),
    "C": ("scanf", "printf"),
    "C++": ("cin >>", "cout <<"),
    "Java": ("Scanner", "System.out.print"),
    "JavaScript": ("readline", "console.log"),
    "Rust": ("read_line", "println!"),
    "Ruby": ("gets", "puts"),
}

LANG_HINTS = {                  # where the generic advice would be wrong for the language
    ("int-division", "C"): "in C, int / int throws the remainder away: make one side a double, "
                           "e.g. (double)total / n, and print it with %f",
    ("int-division", "C++"): "in C++, int / int throws the remainder away: make one side a double, "
                             "e.g. (double)total / n",
    ("int-division", "Java"): "in Java, int / int throws the remainder away: cast one side, "
                              "e.g. (double) total / n",
    ("float-division", "C"): "a decimal where a whole number was expected: use an int, or print with %.0f",
    ("float-division", "Java"): "a decimal where a whole number was expected: use an int, or cast with (int)",
    ("rounding", "C"): "off in the last decimal place: printf's %.2f rounds for you, so do the rounding "
                       "when you print, not before",
    ("rounding", "C++"): "off in the last decimal place: let setprecision round when you print, not before",
    ("rounding", "Java"): "off in the last decimal place: printf(\"%.2f\") rounds for you, so round when "
                          "you print, not before",
    ("off-by-one", "C"): "differs by exactly 1: check the for loop bounds, or where a counter starts",
    ("off-by-one", "Java"): "differs by exactly 1: check the for loop bounds, or where a counter starts",
    ("int-division", "Rust"): "integer division throws the remainder away: make the values f64, "
                              "e.g. total as f64 / n as f64",
    ("int-division", "Ruby"): "Integer#/ throws the remainder away: use to_f on one side, e.g. total.to_f / n",
    ("rounding", "Rust"): "off in the last decimal place: {:.2} rounds for you, so round when you print",
    ("rounding", "Ruby"): "off in the last decimal place: '%.2f' % x rounds for you, so round when you print",
}


def speak(text, lang):
    """Say input()/print() in the language of the program being tested."""
    if not text or lang == "Python":
        return text
    read, write = CALLS.get(lang, CALLS["Python"])
    return text.replace("input()", read).replace("print()", write)


def hint_for(kind, issue=None, source=None):
    lang = source.lang if source else "Python"
    precise, replaces = source_hint(kind, issue, source) if source else (None, False)
    if precise and replaces:
        return precise
    text = None
    if kind == "crash" and issue:
        for pat, hint in CRASH_HINTS:
            if re.search(pat, issue.get("detail") or ""):
                text = hint
                break
    if text is None and kind == "number-format" and issue and issue.get("want") and issue.get("got"):
        for w, g in zip(split_numbers(issue["want"])[0], split_numbers(issue["got"])[0]):
            if w == g:
                continue
            wd, gd = num_decimals(w), num_decimals(g)
            if wd != gd:
                text = (f"expected a whole number: use {format_fix(lang, 0)}" if wd == 0 else
                        f"print with {wd} decimal place{'s' if wd != 1 else ''}, "
                        f"e.g. {format_fix(lang, wd)} (it rounds for you)")
            elif "," in w and "," not in g:
                text = ('use a thousands separator, e.g. f"{x:,}"' if lang == "Python" else
                        "use a thousands separator (printf's %\'d, or build it yourself)")
            elif "," in g and "," not in w:
                text = "drop the thousands separator"
            break
    if text is None:
        text = LANG_HINTS.get((kind, lang), KINDS[kind][1])
    return speak(text, lang) + (" " + precise if precise else "")


def diagnose(path, r, opts, source=None):
    """Work out why an example failed: r.reason/detail/hint, one issue per problem, and tagged diff blocks."""
    ex = r.example
    r.blocks = diff_blocks(ex.expected, r.actual)
    if r.timed_out:
        r.reason = "timeout"
        r.detail = f"timed out after {opts.timeout:g}s (infinite loop, or waiting on input?)"
    else:
        exc, where = crash_info(path, r.stderr) if r.code not in (0, None) else (None, None)
        if exc and not (r.ran_out and exc.startswith("EOFError")):
            r.reason, r.where = "crash", where or 0
            r.detail = f"crashed with {exc}" + (f" ({path.name} line {where})" if where else "")
        elif r.code is not None and r.code < 0:
            r.reason = "crash"
            r.detail = f"crashed with {signal_name(-r.code)}"
            first = next((ln for ln in r.stderr.strip().splitlines() if ln.strip()), "")
            if first:
                r.detail += f": {first.strip()}"
        elif r.ran_out:
            r.reason, r.detail = "input", "program asked for more input than the example provides"
        elif r.used < len(ex.inputs):
            r.reason = "input"
            r.detail = f"program only read {r.used} of {len(ex.inputs)} inputs (did it stop early?)"
    if r.reason:
        r.issues = [dict(kind=r.reason, label=KINDS[r.reason][0], kinds=[r.reason],
                         line=r.where or ex.line, want=None, got=None, detail=r.detail)]
        r.hint = hint_for(r.reason, r.issues[0], source)
        return
    for i1, pairs in r.blocks:
        for k, (want, got, kinds) in enumerate(pairs):
            at = i1 + k if want is not None else i1
            line = ex.at[min(at, len(ex.at) - 1)] if ex.at else ex.line
            r.issues.append(dict(kind=kinds[0], label=KINDS[kinds[0]][0], kinds=kinds,
                                 line=line, want=want, got=got))
    counts = kind_counts(r.issues) or [("wording", 1)]
    r.reason = counts[0][0]
    r.detail = ", ".join(f"{KINDS[k][0]} ({n} line{'s' if n > 1 else ''})" for k, n in counts)
    r.hint = hint_for(r.reason, next((i for i in r.issues if r.reason in i["kinds"]), None), source)


def file_summary(results, source=None):
    """Which kind of mistake dominates a file's failures (None when nothing failed)."""
    failing = [r for r in results if not r.passed]
    issues = [i for r in failing for i in r.issues]
    if not issues:
        return None
    counts = kind_counts(issues)
    kind, n = counts[0]
    rep = next(i for i in issues if kind in i["kinds"])
    in_ex = sum(1 for r in failing if any(kind in i["kinds"] for i in r.issues))
    return dict(kind=kind, label=KINDS[kind][0], count=n, lines=len(issues), examples=in_ex,
                failing=len(failing), counts=counts, detail=rep.get("detail"), hint=hint_for(kind, rep, source),
                consistent=n >= 2 and n >= 0.6 * len(issues) and in_ex >= min(2, len(failing)))


# ----------------------------------------------------------------- reading the source
# Knowing what the program actually prints and reads makes two things possible: telling a
# real input line apart from an output line that merely looks like one (the ": " marker
# problem), and pointing a hint at the exact print statement that needs changing.
@dataclass
class Source:
    reads: list = field(default_factory=list)    # dicts: line, prompt, slots
    prints: list = field(default_factory=list)   # dicts: line, text (numbers as '#'), specs
    lang: str = "Python"

    @property
    def min_reads(self):
        return len(self.reads)

    @property
    def max_reads(self):
        return sum(max(1, r["slots"]) for r in self.reads)


PRINTF_SPEC = r"%[-+ #0']*[\d*]*(?:\.\d+|\.\*)?(?:hh|h|ll|l|L|q|j|z|t)?[diouxXeEfFgGaAcspn%]"
BRACE_SPEC = r"\{[^{}]*\}"                      # Rust's {:.2}
DOLLAR_SPEC = r"\$\{[^{}]*\}"                  # a JavaScript template slot
HASH_SPEC = r"#\{[^{}]*\}"                      # Ruby interpolation
SPEC_RE = re.compile(PRINTF_SPEC)
RUST_SPEC_RE = re.compile(BRACE_SPEC)
JS_SPEC_RE = re.compile(DOLLAR_SPEC)
RUBY_SPEC_RE = re.compile(HASH_SPEC + "|" + PRINTF_SPEC)

C_STR = r'"((?:[^"\\\n]|\\.)*)"'
SQ_STR = r"'((?:[^'\\\n]|\\.)*)'"
BT_STR = r"`((?:[^`\\]|\\.)*)`"
C_OUT_RE = re.compile(r"\b(?:printf|puts|fputs|fprintf)\s*\(\s*(?:stdout\s*,\s*)?" + C_STR)
C_IN_RE = re.compile(r"\b(scanf|fscanf|sscanf|fgets|gets|getchar|getline)\s*\(([^;]{0,400})")
CPP_OUT_RE = re.compile(r"(?:\b(?:printf|fprintf|puts|fputs)\s*\(\s*(?:stdout\s*,\s*)?|<<\s*)" + C_STR)
CPP_IN_RE = re.compile(r"\b(cin\s*>>|scanf|fscanf|getline)([^;]{0,400})")
JAVA_OUT_RE = re.compile(r"System\.out\.print(?:ln|f)?\s*\(\s*" + C_STR)
JAVA_IN_RE = re.compile(r"\.\s*(nextInt|nextDouble|nextFloat|nextLong|nextBoolean|nextLine|next|readLine)\s*\(")
JS_OUT_RE = re.compile(r"console\.(?:log|info|write)\s*\(\s*(?:" + C_STR + "|" + SQ_STR + "|" + BT_STR + ")")
JS_IN_RE = re.compile(r"\b(?:question|prompt|readlineSync\.\w+|createInterface)\s*\(")
RUST_OUT_RE = re.compile(r"\b(?:println!|print!|eprintln!)\s*\(\s*" + C_STR)
RUST_IN_RE = re.compile(r"\bread_line\s*\(")
RUBY_OUT_RE = re.compile(r"\b(?:puts|print|printf)\s*\(?\s*(?:" + C_STR + "|" + SQ_STR + ")")
RUBY_IN_RE = re.compile(r"\bgets\b")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "", "\\": "\\", '"': '"', "'": "'", "a": "", "b": ""}


def unescape(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(ESCAPES.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def print_lines(text, line, spec_re=SPEC_RE):
    """One entry per line a single print statement puts on screen, values blanked to '#'."""
    out = []
    for piece in unescape(text).split("\n"):
        specs = [m.group(0) for m in spec_re.finditer(piece) if m.group(0) != "%%"]
        skeleton = spec_re.sub(lambda m: "%" if m.group(0) == "%%" else "#", piece)
        skeleton = NUM_RE.sub("#", skeleton)
        if skeleton.strip():
            out.append(dict(line=line, text=norm_skeleton(skeleton), specs=specs, raw=piece))
    return out


def norm_skeleton(s):
    return re.sub(r"[ \t]+", " ", s.translate(DASHES).translate(QUOTES)).strip()


def line_at(src, pos):
    return src.count("\n", 0, pos) + 1


def scan_events(src, out_re, in_re, slots=None, spec_re=SPEC_RE):
    """Walk output and read calls in source order; a read's prompt is the text printed just before it."""
    s = Source()
    events = [(m.start(), "out", m) for m in out_re.finditer(src)]
    events += [(m.start(), "in", m) for m in in_re.finditer(src)]
    pending = []
    for pos, kind, m in sorted(events, key=lambda e: e[0]):
        if kind == "out":
            text = next((g for g in m.groups() if g is not None), "")
            s.prints.extend(print_lines(text, line_at(src, pos), spec_re))
            pending.append(unescape(text))
        else:
            tail = "".join(pending)
            prompt = norm_skeleton(NUM_RE.sub("#", spec_re.sub("#", tail.split("\n")[-1])))
            s.reads.append(dict(line=line_at(src, pos), prompt=prompt,
                                slots=slots(m) if slots else 1))
            pending = []
    return s


CPP_STREAM_RE = re.compile(r"\b(?:std\s*::\s*)?(?:cout|clog)\s*((?:<<[^;]*?)+);", re.S)


def split_stream(chain):
    """Break "<< a << b" into its items, ignoring << inside strings or brackets."""
    items, buf, i, depth, quote = [], "", 0, 0, ""
    while i < len(chain):
        c = chain[i]
        if quote:
            buf += c
            if c == "\\" and i + 1 < len(chain):
                buf += chain[i + 1]
                i += 1
            elif c == quote:
                quote = ""
        elif c in "\"'":
            quote, buf = c, buf + c
        elif c in "([":
            depth, buf = depth + 1, buf + c
        elif c in ")]":
            depth, buf = max(0, depth - 1), buf + c
        elif not depth and chain.startswith("<<", i):
            items.append(buf.strip())
            buf, i = "", i + 2
            continue
        else:
            buf += c
        i += 1
    items.append(buf.strip())
    return [x for x in items if x]


def cpp_source(src):
    """C++ output, following each cout << ... chain so a whole printed line can be matched."""
    s = scan_events(src, CPP_OUT_RE, CPP_IN_RE, cpp_slots)
    s.prints = []
    for m in CPP_STREAM_RE.finditer(src):
        line = line_at(src, m.start())
        text, specs, prec = "", [], None
        for item in split_stream(m.group(1)):
            lit = re.fullmatch(C_STR, item)
            if lit:
                text += unescape(lit.group(1))
                continue
            if re.fullmatch(r"(?:std\s*::\s*)?endl", item):
                text += "\n"
                continue
            sp = re.fullmatch(r"(?:std\s*::\s*)?setprecision\s*\(\s*(\d+)\s*\)", item)
            if sp:
                prec = int(sp.group(1))
                continue
            if re.fullmatch(r"(?:std\s*::\s*)?(?:fixed|scientific|showpoint|left|right|flush|boolalpha)", item):
                continue
            if re.fullmatch(r"(?:std\s*::\s*)?setw\s*\(\s*\d+\s*\)", item):
                continue
            text += "#"
            specs.append(f"setprecision({prec})" if prec is not None else "#")
        used = 0
        for piece in text.split("\n"):
            n = piece.count("#")
            skeleton = norm_skeleton(NUM_RE.sub("#", piece))
            if skeleton.strip():
                s.prints.append(dict(line=line, text=skeleton, specs=specs[used:used + n], raw=piece))
            used += n
    if not s.prints:                          # a C++ program that only uses printf
        s.prints = scan_events(src, C_OUT_RE, C_IN_RE, c_slots).prints
    return s


def cpp_slots(m):
    """cin >> a >> b reads two values, and a single typed line can answer both."""
    if m.group(1).startswith("cin"):
        return 1 + m.group(2).count(">>")
    return c_slots(m)


def c_slots(m):
    """How many values one scanf call reads (a single line can answer all of them)."""
    body = m.group(2)
    q = re.search(C_STR, body)
    if m.group(1) in ("fgets", "gets", "getline", "getchar"):
        return 1
    return max(1, len([x for x in SPEC_RE.finditer(q.group(1)) if x.group(0) != "%%"])) if q else 1


def python_source(src):
    s = Source()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return s
    events = []

    def text_of(node):
        """Best-effort text of a print() argument, with values blanked to '#'."""
        if isinstance(node, ast.Constant):
            return str(node.value), []
        if isinstance(node, ast.JoinedStr):
            parts, specs = [], []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value))
                else:
                    parts.append("#")
                    spec = ""
                    if getattr(v, "format_spec", None) is not None:
                        spec = "".join(c.value for c in v.format_spec.values
                                       if isinstance(c, ast.Constant))
                    specs.append("%" + spec if spec else "#")
            return "".join(parts), specs
        return None, []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "print":
            pieces, specs = [], []
            for a in node.args:
                t, sp = text_of(a)
                pieces.append("#" if t is None else t)
                specs += sp
            events.append((node.lineno, node.col_offset, "out", " ".join(pieces), specs))
        elif node.func.id == "input":
            prompt = ""
            if node.args:
                t, _ = text_of(node.args[0])
                prompt = t or ""
            events.append((node.lineno, node.col_offset, "in", prompt, []))
    pending = []
    for line, col, kind, text, specs in sorted(events):
        if kind == "out":
            for piece in text.split("\n"):
                sk = norm_skeleton(NUM_RE.sub("#", piece))
                if sk:
                    s.prints.append(dict(line=line, text=sk, specs=specs, raw=piece))
            pending.append(text)
        else:
            tail = "".join(pending) + text
            s.reads.append(dict(line=line, prompt=norm_skeleton(NUM_RE.sub("#", tail.split("\n")[-1])),
                                slots=1))
            pending = []
    return s


def analyze_source(path, lang):
    """What the program prints and reads, as far as a quick read of the source can tell."""
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return Source()
    name = lang.name if lang else "Python"
    try:
        if lang is None or lang.comments == "docstring":
            got = python_source(src)
        elif name == "C":
            got = scan_events(src, C_OUT_RE, C_IN_RE, c_slots)
        elif name == "C++":
            got = cpp_source(src)
        elif name == "Java":
            got = scan_events(src, JAVA_OUT_RE, JAVA_IN_RE)
        elif name == "JavaScript":
            got = scan_events(src, JS_OUT_RE, JS_IN_RE, spec_re=JS_SPEC_RE)
        elif name == "Rust":
            got = scan_events(src, RUST_OUT_RE, RUST_IN_RE, spec_re=RUST_SPEC_RE)
        elif name == "Ruby":
            got = scan_events(src, RUBY_OUT_RE, RUBY_IN_RE, spec_re=RUBY_SPEC_RE)
        else:
            got = Source()
    except (re.error, RecursionError):
        got = Source()
    got.lang = name
    return got


def prompts_match(a, b):
    """Is the example's prompt the same one the source prints before a read?

    A loose suffix test is not enough: "Distance" is a suffix of "Enter the distance"
    without being the same prompt, so the shorter has to be most of the longer."""
    clean = lambda t: norm_skeleton(NUM_RE.sub("#", t)).lower().rstrip(":>-? ").strip()
    a, b = clean(a), clean(b)
    if not a or not b:
        return False
    if a == b:
        return True
    lo, hi = (a, b) if len(a) <= len(b) else (b, a)
    return hi.endswith(lo) and len(lo) * 3 >= len(hi) * 2


def demote_extras(cands, source):
    """Which candidate input lines are really output lines?

    Needed when a marker like ': ' also appears in ordinary output. A candidate is demoted
    only when its prompt matches no prompt the source reads after, and the whole line is
    exactly what one of the source's print statements produces. Counting is deliberately
    avoided: a read inside a loop answers many input lines, so counts prove nothing."""
    if not source.reads or not source.prints:
        return set()
    drop = set()
    for i, c in enumerate(cands):
        if not c["prompt"].strip():
            continue                          # a bare value on its own line is input
        if any(prompts_match(c["prompt"], r["prompt"]) for r in source.reads):
            continue                          # the program really does read after this prompt
        whole = norm_skeleton(NUM_RE.sub("#", c["line"]))
        if whole and any(pr["text"] == whole for pr in source.prints):
            drop.add(i)                       # a print produces this entire line, value and all
    return drop


def skeleton_re(text):
    """A skeleton like "Hello there, #!" as a pattern: '#' stands for whatever was printed there."""
    if len(text.replace("#", "").strip()) < 4:
        return None                            # too little literal text to identify a line
    return re.compile("".join(".+?" if part == "#" else re.escape(part)
                              for part in re.split(r"(#)", text)) + r"\s*$")


def source_print_for(text, source):
    """The print statement that most likely produced this line of output."""
    want = norm_skeleton(NUM_RE.sub("#", text))
    plain = norm_skeleton(text)
    if not want:
        return None
    best = None
    for pr in source.prints:
        if pr["text"] == want:
            return pr
        if not best and (pr["text"].startswith(want) or want.startswith(pr["text"])) \
                and min(len(pr["text"]), len(want)) >= max(6, len(want) // 2):
            best = pr
    if best:
        return best
    for pr in source.prints:                   # a slot holding text, not a number: "Hello, #!"
        pattern = skeleton_re(pr["text"])
        if pattern and (pattern.match(plain) or pattern.match(want)):
            return pr
    return None


def spec_decimals(spec):
    """How many decimal places a format asks for: %.2f, {:.2}, setprecision(2) -> 2.  None if unclear."""
    m = re.match(r"setprecision\((\d+)\)$", spec)
    if m:
        return int(m.group(1))
    m = re.match(r"%[-+ #0']*\d*\.(\d+)", spec)
    if m:
        return int(m.group(1))
    m = re.search(r"\.(\d+)[a-zA-Z]?\}$", spec)
    if m:
        return int(m.group(1))
    if re.match(r"%[-+ #0']*\d*[diu]", spec):
        return 0
    return None


def format_fix(lang, dp):
    """How to ask for DP decimal places in this language."""
    if lang == "Python":
        return f'f"{{x:.{dp}f}}"'
    if lang == "Java":
        return f'System.out.printf("%.{dp}f", x)'
    if lang == "JavaScript":
        return f"x.toFixed({dp})"
    if lang == "Rust":
        return "{:." + str(dp) + "}"
    if lang == "Ruby":
        return f"'%.{dp}f' % x"
    if lang == "C++":
        return f"<< fixed << setprecision({dp})"
    return f'%.{dp}f'


def source_hint(kind, issue, source):
    """(hint, replaces the generic one?) naming the exact print statement to change."""
    if not source or not source.prints or not issue or not issue.get("want"):
        return None, False
    pr = source_print_for(issue["want"], source)
    if not pr and issue.get("got"):
        pr = source_print_for(issue["got"], source)   # a wording bug prints the wrong words
    if not pr:
        return None, False
    where = f"line {pr['line']}"
    if kind == "number-format":            # the value is right, only the format is wrong
        wn, gn = split_numbers(issue["want"])[0], split_numbers(issue.get("got") or "")[0]
        for k, w in enumerate(wn):
            if k < len(gn) and gn[k] == w:
                continue
            dp = num_decimals(w)
            spec = pr["specs"][k] if k < len(pr["specs"]) else None
            if spec == "#":                            # printed with no formatting at all
                return (f"{where} prints this value with no formatting; ask for "
                        f"{dp} decimal place{'s' if dp != 1 else ''} with {format_fix(source.lang, dp)}"), True
            if spec and spec != "#":
                have = spec_decimals(spec)
                if have is not None and have != dp:
                    return (f"{where} prints {spec}, but the example shows "
                            f"{dp} decimal place{'s' if dp != 1 else ''}: use {format_fix(source.lang, dp)}"), True
            return f"({where} prints it)", False
        return f"({where} prints it)", False
    if kind in ("case", "spacing", "punctuation", "wording"):
        return f"{where} is the print to change: it should read {issue['want']!r}", True
    return f"({where} prints it)", False


# ----------------------------------------------------------------- testing a file
@dataclass
class FileResult:
    path: Path
    results: list = None      # None: no examples found
    error: str = ""           # e.g. a syntax error or a failed build: nothing could run
    error_line: int = 0
    error_col: int = 0
    passed: int = 0
    total: int = 0
    summary: dict = None
    lang: Language = None
    diags: list = field(default_factory=list)      # compiler errors
    warnings: list = field(default_factory=list)   # compiler warnings from a build that worked


def test_file(path, opts):
    fr = FileResult(path)
    try:
        fr.lang = lang_for(path, opts.lang)
    except ValueError as e:
        fr.error, fr.error_line, fr.error_col, fr.total = str(e), 1, 1, 1
        return fr
    try:
        doc, start = find_transcript(path, fr.lang)
    except SyntaxError as e:
        fr.error = f"cannot parse file: {e}"
        fr.error_line, fr.error_col, fr.total = e.lineno or 1, e.offset or 1, 1
        return fr
    except (OSError, UnicodeDecodeError) as e:
        fr.error, fr.error_line, fr.error_col, fr.total = f"cannot read file: {e}", 1, 1, 1
        return fr
    if not doc:
        return fr
    source = Source() if opts.no_source else analyze_source(path, fr.lang)
    examples = parse_examples(doc, opts, start, source)
    if opts.examples:
        examples = [e for e in examples if e.number in opts.examples]
    prog = build_program(path, opts)
    fr.diags, fr.warnings = prog.diags, prog.warnings
    if prog.error:
        fr.error, fr.total = prog.error, max(1, len(examples))
        fr.error_line = prog.diags[0][1] if prog.diags else 1
        fr.error_col = prog.diags[0][2] if prog.diags else 1
        cleanup(prog)
        return fr
    fr.results = []
    try:
        for ex in examples:
            r = run_example(prog, ex, opts)
            if not r.passed:
                diagnose(path, r, opts, source)
            fr.results.append(r)
    finally:
        cleanup(prog)
    fr.passed = sum(r.passed for r in fr.results)
    fr.total = len(fr.results)
    fr.summary = file_summary(fr.results, source)
    return fr


def cleanup(prog):
    if prog.tmp:
        shutil.rmtree(prog.tmp, ignore_errors=True)
        prog.tmp = ""


# ----------------------------------------------------------------- report (terminal)
def indent(text, n=8):
    return "\n".join(" " * n + ln for ln in text.splitlines())


def term_width():
    return max(40, shutil.get_terminal_size((80, 24)).columns)


def wrapped(label, text, width, pad="      ", color=None, prose=False):
    """One labelled line, wrapped with a hanging indent so long prompts stay readable.
    prose=True for explanations (whitespace is not significant there)."""
    body = pad + " " * (len(label) + 1)
    lines = textwrap.wrap(text or "(empty line)", width=width,
                          initial_indent=pad + label + " ", subsequent_indent=body,
                          break_long_words=True, break_on_hyphens=False,
                          replace_whitespace=prose, drop_whitespace=prose) or [pad + label]
    if color:
        lines[0] = pad + color(label) + lines[0][len(pad) + len(label):]
    return "\n".join(lines)


def print_compact_diff(blocks, width):
    """want/got pairs instead of a unified diff: easier to read in a narrow pane."""
    for i1, pairs in blocks:
        kinds = list(dict.fromkeys(k for _, _, ks in pairs for k in ks))
        print(dim(f"      line {i1 + 1} ({', '.join(KINDS[k][0] for k in kinds)}):"))
        for want, got, _ in pairs:
            if want is not None and got is not None:
                print(wrapped("want:", want, width, color=green))
                print(wrapped("got: ", got, width, color=red))
            elif want is not None:
                print(wrapped("miss:", want, width, color=red))   # program never printed this
            else:
                print(wrapped("extra", got, width, color=red))    # program printed this unexpectedly


def print_unified_diff(expected, actual, context):
    for ln in difflib.unified_diff(expected, actual, "expected", "actual", lineterm="", n=context):
        if ln.startswith("+") and not ln.startswith("+++"):
            ln = green(ln)
        elif ln.startswith("-") and not ln.startswith("---"):
            ln = red(ln)
        print("      " + ln)


def program_stderr(r, opts):
    """The program's own traceback lines (the tester's wrapper frames hidden unless verbose)."""
    err = r.stderr.rstrip().splitlines()
    if not opts.verbose:
        keep, skip = [], False
        for ln in err:
            if ln.lstrip().startswith("File "):
                skip = "<string>" in ln or "<frozen runpy>" in ln
            if not skip or not ln.startswith(" "):
                keep.append(ln)
        err = keep
    return "\n".join(err)


def report_file(fr, opts):
    width = term_width()
    tag = f"   {dim('[' + fr.lang.name + ']')}" if fr.lang and fr.lang.name != "Python" else ""
    print(bold(f"\n== {fr.path}") + tag)
    for f, line, col, sev, msg in fr.warnings[:6]:
        print(wrapped("note:", f"line {line}: {msg}", width, color=yellow, prose=True))
    if fr.error:
        print(red(f"   {fr.error}"))
        for f, line, col, sev, msg in fr.diags[:12]:
            print(wrapped(f"{sev}:", f"line {line}: {msg}", width, color=red, prose=True))
        return
    if fr.results is None:
        print(yellow("   no 'Example execution' blocks found"))
        return
    s = fr.summary
    summarized = bool(s and s["consistent"] and s["failing"] >= 2)   # the hint is printed once, at the end
    for r in fr.results:
        ex = r.example
        label = f"Example {ex.number}"
        inputs = ", ".join(ex.inputs) or "(no input)"
        if r.passed:
            print(f"   {green('PASS')}  {label}")
            if opts.verbose:
                print(dim(indent("\n".join(r.actual), 6)))
            continue

        head = f"   {red('FAIL')}  {label}"
        if len(f"   FAIL  {label}   [{inputs}]") <= width:
            print(f"{head}   {dim('[' + inputs + ']')}")
        else:
            print(head)
            print(wrapped("in:  ", inputs, width, color=dim))
        print(wrapped("why: ", r.detail, width, color=yellow, prose=True))
        if r.hint and not (summarized and r.reason == s["kind"]):
            print(wrapped("hint:", r.hint, width, color=cyan, prose=True))

        if opts.unified:
            print_unified_diff(ex.expected, r.actual, opts.context)
        else:
            print_compact_diff(r.blocks, width)

        if opts.verbose:
            print(dim("      --- full expected ---"))
            print(dim(indent("\n".join(ex.expected), 8)))
            print(dim("      --- full actual ---"))
            print(dim(indent("\n".join(r.actual), 8)))
        if r.stderr.strip() and (r.code not in (0, None) or opts.verbose):
            print(yellow(f"      error (exit code {r.code}):"))
            print(indent(program_stderr(r, opts), 8))

    summary = f"   {fr.passed}/{fr.total} passed"
    print(bold(green(summary) if fr.passed == fr.total else red(summary)))
    if summarized:
        what = f"{s['label']}: {s['detail']}" if s["kind"] in STRUCTURAL else s["label"]
        print(yellow(bold(f"   Consistent issue: {what}")))
        where = (f"in {s['examples']} of {s['failing']} failing examples" if s["kind"] in STRUCTURAL else
                 f"{s['count']} of {s['lines']} mismatched lines, in {s['examples']} of {s['failing']} failing examples")
        print(dim(f"      {where}"))
        print(wrapped("hint:", s["hint"], width, color=cyan, prose=True))
    elif s and s["failing"] >= 2 and len(s["counts"]) > 1:
        print(yellow("   Mixed issues: " + ", ".join(f"{KINDS[k][0]} x{n}" for k, n in s["counts"])))


# ----------------------------------------------------------------- report (editors and tools)
def problem_lines(fr):
    """One 'file:line:col: severity: message' per problem, for editors and VS Code's problem matcher."""
    p = str(fr.path)
    for f, line, col, sev, msg in fr.warnings:
        yield f"{p}:{line}:{col}: warning: {msg}"
    if fr.error:
        if fr.diags:
            for f, line, col, sev, msg in fr.diags:
                yield f"{p}:{line}:{col}: {sev}: {msg}"
        else:
            yield f"{p}:{fr.error_line}:{fr.error_col}: error: {fr.error}"
        return
    if fr.results is None:
        yield f"{p}:1:1: info: no 'Example execution' blocks found"
        return
    for r in fr.results:
        if r.passed:
            continue
        n = r.example.number
        for i in r.issues:
            if i["want"] is None and i["got"] is None:
                msg = f"Example {n}: {i['detail']}"
            elif i["got"] is None:
                msg = f'Example {n}: missing line: "{i["want"]}"'
            elif i["want"] is None:
                msg = f'Example {n}: extra line: "{i["got"]}"'
            else:
                msg = f'Example {n}: {KINDS[i["kind"]][0]}: want "{i["want"]}" got "{i["got"]}"'
            yield f"{p}:{i['line']}:1: error: {msg}"
        yield f"{p}:{r.example.line}:1: warning: Example {n} failed: {r.detail}. Hint: {r.hint}"
    s = fr.summary
    if s and s["consistent"] and s["failing"] >= 2:
        first = next(r.example.line for r in fr.results if not r.passed)
        what = f"{s['label']}: {s['detail']}" if s["kind"] in STRUCTURAL else s["label"]
        yield f"{p}:{first}:1: warning: Consistent issue across {s['examples']} examples: {what}. Hint: {s['hint']}"


def file_json(fr):
    d = dict(path=str(fr.path), language=fr.lang.name if fr.lang else None,
             error=fr.error or None, error_line=fr.error_line or None,
             diagnostics=[dict(line=l, column=c, severity=sv, message=m) for _, l, c, sv, m in fr.diags],
             warnings=[dict(line=l, column=c, severity=sv, message=m) for _, l, c, sv, m in fr.warnings],
             passed=fr.passed, total=fr.total, examples=None if fr.results is None else [], summary=None)
    for r in fr.results or []:
        ex = r.example
        d["examples"].append(dict(
            number=ex.number, line=ex.line, passed=r.passed, inputs=ex.inputs,
            expected=ex.expected, actual=r.actual, inputs_used=r.used,
            exit_code=r.code, timed_out=r.timed_out, stderr=r.stderr,
            reason=r.reason or None, detail=r.detail or None, hint=r.hint or None, issues=r.issues))
    if fr.summary:
        d["summary"] = dict(fr.summary, counts=[list(kv) for kv in fr.summary["counts"]])
    return d


# ----------------------------------------------------------------- VS Code (no extension needed)
PROBLEM_MATCHER = {
    "owner": "autotester",
    "fileLocation": ["autoDetect", "${workspaceFolder}"],
    "pattern": {
        "regexp": "^(.+?):(\\d+):(\\d+): (error|warning|info): (.*)$",
        "file": 1, "line": 2, "column": 3, "severity": 4, "message": 5,
    },
}


def setup_vscode(folder):
    """Write FOLDER/.vscode/tasks.json: Ctrl/Cmd+Shift+B tests the open file, mismatches land in Problems."""
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        print(red(f"not a folder: {folder}"))
        return 1
    me = str(Path(__file__).resolve())

    def task(label, target, default):
        return {
            "label": label, "type": "process", "command": sys.executable,
            "args": [me, target, "--problems"],
            "group": {"kind": "build", "isDefault": True} if default else "build",
            "presentation": {"reveal": "always", "panel": "dedicated", "clear": True, "showReuseMessage": False},
            "problemMatcher": PROBLEM_MATCHER,
        }

    mine = [task("Autotester: test current file", "${file}", True),
            task("Autotester: test whole folder", "${workspaceFolder}", False)]
    target = folder / ".vscode" / "tasks.json"
    data = {"version": "2.0.0", "tasks": []}
    if target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
        except (ValueError, AssertionError):
            print(yellow(f"{target} exists and is not plain JSON (comments?). Add these tasks to it yourself:"))
            print(json.dumps(mine, indent=2))
            return 1
        labels = {t["label"] for t in mine}
        data["tasks"] = [t for t in data.get("tasks", []) if t.get("label") not in labels] + mine
    else:
        data["tasks"] = mine
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(green(f"wrote {target}"))
    print(f"  runs {me}\n  with {sys.executable}")
    print("In VS Code: open a program and press Ctrl+Shift+B (Cmd+Shift+B on Mac).")
    print("Results show in the terminal; each mismatch is also in the Problems panel and clicking it")
    print("jumps to that line of the docstring example.")
    return 0


# ----------------------------------------------------------------- project settings
CONFIG_NAMES = ("autotester.json", ".autotester.json")
CONFIG_KEYS = {"input_marker", "timeout", "strict", "keep_blank", "ignore", "lang",
               "quiet", "python", "no_pty", "no_source", "unified", "context", "examples"}


def find_config(start):
    """The nearest autotester.json at or above START, as (settings, path)."""
    here = Path(start).resolve()
    here = here if here.is_dir() else here.parent
    for folder in [here, *here.parents]:
        for name in CONFIG_NAMES:
            f = folder / name
            if f.is_file():
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except ValueError as e:
                    print(red(f"{f}: not valid JSON ({e})"), file=sys.stderr)
                    return {}, None
                if not isinstance(data, dict):
                    print(red(f"{f}: expected a JSON object"), file=sys.stderr)
                    return {}, None
                bad = set(data) - CONFIG_KEYS
                if bad:
                    print(yellow(f"{f}: ignoring unknown setting(s) "
                                 + ", ".join(sorted(bad))), file=sys.stderr)
                return {k: v for k, v in data.items() if k in CONFIG_KEYS}, f
    return {}, None


def opts_for(path, opts, defaults):
    """OPTS with an autotester.json near PATH filled in; anything typed on the command line wins."""
    if opts.no_config:
        return opts
    settings, where = find_config(path)
    if not settings:
        return opts
    merged = argparse.Namespace(**vars(opts))
    for key, value in settings.items():
        if getattr(merged, key, None) == defaults.get(key):     # untouched on the command line
            setattr(merged, key, value)
    merged.config_file = str(where)
    return merged


# ----------------------------------------------------------------- CLI
def pick_paths():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        files = filedialog.askopenfilenames(
            title="Choose Python file(s) to test",
            filetypes=[("Programs", " ".join("*" + x for x in sorted(SUFFIXES))),
                       ("Python files", "*.py"), ("All files", "*")])
        root.destroy()
        return [Path(f) for f in files]
    except Exception:
        s = input("Path to a .py file or folder: ").strip().strip("'\"")
        return [Path(s)] if s else []


def collect(paths):
    me = Path(__file__).resolve()
    mine = me.parent          # this folder's own samples are meant to fail: only test them on request
    out = []
    for p in paths:
        p = p.expanduser()
        if p.is_dir():
            root = p.resolve()
            asked_for_mine = root == mine or mine in root.parents
            for f in sorted(x for x in p.rglob("*") if x.suffix.lower() in BY_SUFFIX):
                rf = f.resolve()
                if rf == me or SKIP_DIRS & set(f.relative_to(p).parts):
                    continue
                if not asked_for_mine and mine in rf.parents:
                    continue
                try:
                    if find_transcript(f)[0]:
                        out.append(f)
                except SyntaxError:                       # still report it if it holds examples
                    if HEADER_RE.search(f.read_text(encoding="utf-8", errors="replace")):
                        out.append(f)
                except (OSError, UnicodeDecodeError):
                    pass
        elif p.is_file():
            out.append(p)
        else:
            print(red(f"not found: {p}"), file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description="Test Python programs against the "
                                 "'Example execution' transcripts in their docstrings.")
    ap.add_argument("paths", nargs="*", type=Path, help="files or folders (omit to pick with a dialog)")
    ap.add_argument("-e", "--examples", nargs="+", type=int, metavar="N", help="only run these example numbers")
    ap.add_argument("-v", "--verbose", action="store_true", help="show full output and stderr")
    ap.add_argument("-t", "--timeout", type=float, default=5.0, help="seconds per example (default 5)")
    ap.add_argument("-u", "--unified", action="store_true", help="show a classic unified diff instead of want/got lines")
    ap.add_argument("-c", "--context", type=int, default=2, help="diff context lines with --unified (default 2)")
    ap.add_argument("--strict", action="store_true",
                    help="exact matching: no prompt/dash/quote/whitespace normalization")
    ap.add_argument("--keep-blank", action="store_true", help="compare blank lines too")
    ap.add_argument("--ignore", action="append", default=[], metavar="REGEX",
                    help="skip docstring lines matching REGEX (repeatable)")
    ap.add_argument("--input-marker", metavar="REGEX",
                    help="regex that marks typed input in an example line (default: an arrow such as '-> '); "
                         "the text before the match is the prompt, the text after it is what gets typed")
    ap.add_argument("--python", default=sys.executable, help="interpreter used to run Python programs")
    ap.add_argument("--lang", metavar="NAME",
                    help="force a language instead of going by the file suffix ("
                         + ", ".join(L.name.lower() for L in LANGUAGES) + ")")
    ap.add_argument("--quiet", type=float, default=0.2, metavar="SEC",
                    help="for non-Python programs: how long to wait for a prompt before typing (default 0.2)")
    ap.add_argument("--no-source", action="store_true",
                    help="do not read the program's source for sharper hints and input detection")
    ap.add_argument("--no-pty", action="store_true",
                    help="do not use a pseudo-terminal for non-Python programs (prompts may appear late)")
    ap.add_argument("--json", action="store_true",
                    help="print the results as JSON instead of the report (for editors, plugins, scripts)")
    ap.add_argument("--problems", action="store_true",
                    help="after each report, print one 'file:line:col: message' per problem (editors, VS Code)")
    ap.add_argument("--vscode", nargs="?", const=".", metavar="FOLDER",
                    help="write FOLDER/.vscode/tasks.json so Ctrl/Cmd+Shift+B tests the open file (default: here)")
    ap.add_argument("--no-config", action="store_true",
                    help="ignore any autotester.json found next to the programs")
    ap.add_argument("--no-color", action="store_true")
    opts = ap.parse_args()
    opts.config_file = None
    defaults = {a.dest: a.default for a in ap._actions}

    C.on = sys.stdout.isatty() and not opts.no_color and not opts.json and os.environ.get("NO_COLOR") is None
    if C.on and os.name == "nt":
        os.system("")  # enable ANSI colors in Windows terminals
    if opts.vscode is not None:
        return setup_vscode(opts.vscode)

    files = collect(opts.paths or pick_paths())
    if not files:
        print(json.dumps(dict(files=[], passed=0, total=0)) if opts.json else "Nothing to test.")
        return 1

    reports, tp, tt = [], 0, 0
    shown = set()
    for f in files:
        fopts = opts_for(f, opts, defaults)
        if fopts.config_file and fopts.config_file not in shown and not fopts.json:
            shown.add(fopts.config_file)
            print(dim(f"using settings from {fopts.config_file}"))
        fr = test_file(f, fopts)
        reports.append(fr)
        tp, tt = tp + fr.passed, tt + fr.total
        if opts.json:
            continue
        report_file(fr, fopts)
        if opts.problems:
            print(dim("      (problem list for the editor)"))
            for ln in problem_lines(fr):
                print(ln)

    if opts.json:
        print(json.dumps(dict(files=[file_json(fr) for fr in reports], passed=tp, total=tt), indent=2))
    elif len(files) > 1:
        line = f"\nTOTAL: {tp}/{tt} examples passed across {len(files)} files"
        print(bold(green(line) if tp == tt else red(line)))
        counts = kind_counts([i for fr in reports for r in fr.results or [] if not r.passed for i in r.issues])
        if counts:
            print(yellow("Most common issues: " + ", ".join(f"{KINDS[k][0]} x{n}" for k, n in counts[:4])))
    return 0 if tp == tt else 1


if __name__ == "__main__":
    sys.exit(main())
