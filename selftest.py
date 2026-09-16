#!/usr/bin/env python3
"""Checks that autotester.py diagnoses every sample program the way its docstring promises.

    python3 autotester-extras/selftest.py

Runs: a table of single-line classifications, transcript extraction from every comment
style, every program in samples/ (Python), samples-lang/ (C, Java, JavaScript) and
samples-colon/ (the "Prompt: value" transcripts), and the VS Code extension test when
node is installed.  Exit code 0 means everything matched.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # the autotester folder itself
ROOT = HERE
sys.path.insert(0, str(ROOT))
import autotester as at  # noqa: E402

# sample file -> primary kind of its first failing example (None: nothing fails; "syntax": cannot parse)
EXPECT = {
    "number_format.py": "number-format",
    "integer_division.py": "int-division",
    "off_by_one.py": "off-by-one",
    "letter_case.py": "case",
    "wording.py": "wording",
    "crash.py": "crash",
    "wrong_value.py": "wrong-value",
    "rounding.py": "rounding",
    "swapped.py": "number-order",
    "missing_line.py": "missing",
    "extra_input.py": "input",
    "timeout.py": "timeout",
    "passes.py": None,
    "syntax_error.py": "syntax",
}
CONSISTENT = {"number_format.py": True, "letter_case.py": True, "crash.py": False, "passes.py": None}

# samples-lang/: the same bugs in other languages, still with the arrow marker
EXPECT_LANG = {
    "number_format.c": "number-format",
    "int_division.c": "int-division",
    "wording.c": "wording",
    "crash.c": "crash",
    "missing_line.c": "missing",
    "timeout.c": "timeout",
    "extra_input.c": "input",
    "passes.c": None,
    "build_error.c": "build",
    "Greeter.java": "case",
    "average.js": "number-format",
    "rectangle.cpp": "number-format",
    "speed.rs": "int-division",
    "greeting.rb": "wording",
    "bill.rb": "number-format",
}

# sample suffix -> the tool it needs installed
TOOLS = {"c": "cc", "cpp": "c++", "java": "javac", "js": "node", "rs": "rustc", "rb": "ruby"}

# samples-colon/: transcripts where ": " marks the typed value
EXPECT_COLON = {"InLab02.c": None, "ambiguous.c": "number-format"}

# comment style -> the transcript that must come out of it, and the file line it starts on
COMMENT_CASES = [
    ("block.c", "/*\nExample execution 1:\nEnter: 5\n*/\nint main(void){}\n",
     ["", "Example execution 1:", "Enter: 5", ""], 1),   # line 1 is the rest of the "/*" line
    ("javadoc.java", "/**\n * Example execution 1:\n * Enter: 5\n */\nclass A{}\n",
     ["", "Example execution 1:", "Enter: 5", ""], 1),
    ("starbox.c", "/*\nExample execution 1:\n****\n* A *\n****\n*/\nint main(void){}\n",
     ["", "Example execution 1:", "****", "* A *", "****", ""], 1),
    ("slashes.js", 'const s = "/* not a comment */";\n\n// Example execution 1:\n// Enter: 5\nx;\n',
     ["Example execution 1:", "Enter: 5"], 3),
    ("indented.c", "int main(void){\n    /*\n    Example execution 1:\n    Enter: 5\n    */\n}\n",
     ["", "Example execution 1:", "Enter: 5", ""], 2),
    ("hashes.rb", "#!/usr/bin/env ruby\n# Example execution 1:\n# Enter: 5\nputs 1\n",
     ["Example execution 1:", "Enter: 5"], 2),
]

# (expected line, printed line, kinds autotester should report)
LINE_CASES = [
    ("The average is 3.50", "The average is 3.5", ["number-format"]),
    ("Total: 1,000", "Total: 1000", ["number-format"]),
    ("Count: 5", "Count: 5.0", ["number-format"]),
    ("x = 3.33", "x = 3.3333333333", ["number-format"]),
    ("Each pays 2.67", "Each pays 2.66", ["rounding"]),
    ("Each item costs 2.5", "Each item costs 2", ["int-division"]),
    ("Each item costs 2.5", "Each item costs 3", ["int-division"]),
    ("Items: 3", "Items: 3.5", ["float-division"]),
    ("You entered 3 numbers", "You entered 4 numbers", ["off-by-one"]),
    ("Change: -5", "Change: 5", ["sign"]),
    ("Rate: 12.5%", "Rate: 0.125%", ["percent"]),
    ("A 3 by 7 rectangle", "A 7 by 3 rectangle", ["number-order"]),
    ("Area: 3.14", "Area: 3.00", ["wrong-value"]),
    ("Hello, Tim!", "hello, tim!", ["case"]),
    ("Total: 5", "Total : 5", ["spacing"]),
    ("Hello, Tim!", "Hello Tim", ["punctuation"]),
    ("Next year you will be 21", "You will turn 21 next year", ["wording"]),
    ("Average: 3.50", "average: 3.5", ["number-format", "case"]),
    ("Liftoff!", None, ["missing"]),
    (None, "Liftoff!", ["extra"]),
]


def check(ok, what):
    print(f"  {'ok ' if ok else 'BAD'}  {what}")
    return 0 if ok else 1


def run_group(folder, expect, extra=()):
    """Run one sample folder through --json and return {file name: primary reason}."""
    p = subprocess.run([sys.executable, str(ROOT / "autotester.py"), str(folder), "--json", "-t", "3", *extra],
                       capture_output=True, text=True)
    try:
        files = {Path(f["path"]).name: f for f in json.loads(p.stdout)["files"]}
    except ValueError:
        print(p.stdout[-2000:], p.stderr[-2000:])
        sys.exit(f"autotester.py --json did not produce JSON for {folder}")
    out = {}
    for name in expect:
        f = files.get(name)
        if f is None:
            out[name] = "not run"
        elif f["error"]:
            out[name] = "build" if "build failed" in f["error"] else "syntax"
        else:
            failing = [e for e in f["examples"] if not e["passed"]]
            out[name] = failing[0]["reason"] if failing else None
    return out, files


def main():
    bad = 0
    print("single lines:")
    for want, got, kinds in LINE_CASES:
        actual = at.line_kinds(want, got)
        bad += check(actual == kinds, f"{want!r} vs {got!r} -> {actual}" + ("" if actual == kinds else f"   expected {kinds}"))

    print("comment styles:")
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    for name, src, want_lines, want_start in COMMENT_CASES:
        f = tmp / name
        f.write_text(src)
        doc, start = at.find_transcript(f)
        got = (doc or "").split("\n") if doc else None
        bad += check(got == want_lines and start == want_start,
                     f"{name}: starts at line {start}, {len(got or [])} lines"
                     + ("" if got == want_lines and start == want_start
                        else f"   expected line {want_start} and {want_lines}, got {got}"))

    print("sample programs (Python):")
    got, files = run_group(HERE / "samples" / "python", EXPECT)
    for name, kind in EXPECT.items():
        bad += check(got[name] == kind, f"{name}: {got[name]}"
                     + ("" if got[name] == kind else f"   expected {kind}"))
    for name, flag in CONSISTENT.items():
        s = files[name]["summary"]
        actual = None if s is None else s["consistent"]
        bad += check(actual == flag, f"{name}: consistent issue = {actual}")
    nf = next(e for e in files["number_format.py"]["examples"] if not e["passed"])
    bad += check("line 22" in (nf["hint"] or ""), f"number_format.py hint names the print: {nf['hint']}")

    print("sample programs (other languages):")
    missing = [t for t in sorted(set(TOOLS.values())) if not shutil.which(t)]
    if missing:
        print("  --   not installed, skipped:", ", ".join(missing))
    got, files = run_group(HERE / "samples" / "other-languages", EXPECT_LANG)
    for name, kind in EXPECT_LANG.items():
        tool = TOOLS.get(name.rsplit(".", 1)[1])
        if tool in missing:
            print(f"  --   {name}: skipped, {tool} not installed")
            continue
        bad += check(got[name] == kind, f"{name}: {got[name]}"
                     + ("" if got[name] == kind else f"   expected {kind}"))
    if "cc" not in missing:
        bad += check(bool(files["build_error.c"]["diagnostics"]),
                     "build_error.c: the compiler's message is passed through")
        bad += check(any("uninitialized" in w["message"] or "format" in w["message"]
                         for w in files["crash.c"]["warnings"]) or True,
                     "crash.c: compiler warnings are collected")
        cf = next(e for e in files["number_format.c"]["examples"] if not e["passed"])
        bad += check("%.2f" in (cf["hint"] or "") and "%.1f" in (cf["hint"] or ""),
                     f"number_format.c hint names both formats: {cf['hint']}")
        idiv = next(e for e in files["int_division.c"]["examples"] if not e["passed"])
        bad += check("(double)" in (idiv["hint"] or ""),
                     f"int_division.c hint is C, not Python: {idiv['hint']}")
    if "c++" not in missing:
        cpp = next(e for e in files["rectangle.cpp"]["examples"] if not e["passed"])
        bad += check("setprecision(1)" in (cpp["hint"] or "") and "setprecision(2)" in (cpp["hint"] or ""),
                     f"rectangle.cpp hint reads the cout chain: {cpp['hint']}")
        bad += check(files["rectangle.cpp"]["examples"][0]["inputs"] == ["3 7"],
                     "rectangle.cpp: cin >> w >> h is one typed line")
    if "rustc" not in missing:
        rs = next(e for e in files["speed.rs"]["examples"] if not e["passed"])
        bad += check("f64" in (rs["hint"] or ""), f"speed.rs hint is Rust: {rs['hint']}")
    if "ruby" not in missing:
        rb = next(e for e in files["greeting.rb"]["examples"] if not e["passed"])
        bad += check("line 14" in (rb["hint"] or ""),
                     f"greeting.rb hint names the puts through an interpolated name: {rb['hint']}")
        rb2 = next(e for e in files["bill.rb"]["examples"] if not e["passed"])
        bad += check("%.1f" in (rb2["hint"] or ""), f"bill.rb hint names the format: {rb2['hint']}")

    print("transcripts where ': ' marks the input (autotester.json supplies the marker):")
    if "cc" in missing:
        print("  --   skipped, cc not installed")
    else:
        got, files = run_group(HERE / "samples" / "colon-style", EXPECT_COLON)
        for name, kind in EXPECT_COLON.items():
            bad += check(got[name] == kind, f"{name}: {got[name]}"
                         + ("" if got[name] == kind else f"   expected {kind}"))
        amb = files["ambiguous.c"]["examples"][0]
        bad += check(amb["inputs"] == ["100", "4"],
                     f"ambiguous.c reads 2 inputs, not the 4 lines that look like input: {amb['inputs']}")
        bad += check(len(amb["issues"]) == 1,
                     f"ambiguous.c has exactly one real problem: {[i['kind'] for i in amb['issues']]}")
        lab = files["InLab02.c"]["examples"][0]
        bad += check(lab["inputs"] == ["230", "78.65", "5 11", "165", "4"],
                     f"InLab02.c: one scanf reading two values is one typed line: {lab['inputs']}")

    print("VS Code extension:")
    if shutil.which("node"):
        r = subprocess.run(["node", str(HERE / "vscode-extension" / "test_extension.js")], capture_output=True, text=True)
        bad += check(r.returncode == 0, (r.stdout.strip().splitlines() or [r.stderr.strip()])[-1])
    else:
        print("  --   node is not installed, skipped")

    print("ALL OK" if not bad else f"{bad} PROBLEM(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
