// Exercises extension.js without VS Code: a small stub of the vscode API, the real
// autotester.py and the sample programs.      Run:  node test_extension.js
"use strict";
const Module = require("module");
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..");            // the autotester folder
const SAMPLES = path.join(ROOT, "samples", "python");
const LANGS = path.join(ROOT, "samples", "other-languages");
const COLON = path.join(ROOT, "samples", "colon-style");

// ---------------------------------------------------------------- vscode stub
class Position { constructor(line, character) { this.line = line; this.character = character; } }
class Range { constructor(sl, sc, el, ec) { this.start = new Position(sl, sc); this.end = new Position(el, ec); } }
class Location { constructor(uri, range) { this.uri = uri; this.range = range; } }
class Diagnostic { constructor(range, message, severity) { this.range = range; this.message = message; this.severity = severity; } }
class TestMessage {
  constructor(message) { this.message = message; }
  static diff(message, expectedOutput, actualOutput) {
    const m = new TestMessage(message); m.expectedOutput = expectedOutput; m.actualOutput = actualOutput; return m;
  }
}
class Uri {
  constructor(fsPath) { this.fsPath = fsPath; this.scheme = "file"; }
  static file(p) { return new Uri(p); }
  toString() { return "file://" + this.fsPath; }
}
class ItemCollection {
  constructor(owner) { this.owner = owner; this.map = new Map(); }
  add(item) { item.parent = this.owner; this.map.set(item.id, item); }
  replace(items) { this.map = new Map(); items.forEach((i) => this.add(i)); }
  get(id) { return this.map.get(id); }
  delete(id) { this.map.delete(id); }
  forEach(fn) { this.map.forEach((v) => fn(v)); }
  get size() { return this.map.size; }
}
class TestItem {
  constructor(id, label, uri) { this.id = id; this.label = label; this.uri = uri; this.parent = undefined; this.children = new ItemCollection(this); }
}
class TestRunRequest { constructor(include, exclude, profile) { this.include = include; this.exclude = exclude; this.profile = profile; } }
const runs = [];
class TestRun {
  constructor(request) { this.request = request; this.states = new Map(); this.messages = new Map(); this.output = ""; this.ended = false; runs.push(this); }
  started(i) { this.states.set(i.id, "started"); }
  passed(i) { this.states.set(i.id, "passed"); }
  failed(i, m) { this.states.set(i.id, "failed"); this.messages.set(i.id, m); }
  errored(i, m) { this.states.set(i.id, "errored"); this.messages.set(i.id, m); }
  skipped(i) { this.states.set(i.id, "skipped"); }
  appendOutput(s) { this.output += s; }
  end() { this.ended = true; }
}
const controller = {
  items: new ItemCollection(undefined), profiles: [], resolveHandler: undefined,
  createTestItem: (id, label, uri) => new TestItem(id, label, uri),
  createRunProfile(label, kind, runHandler, isDefault) { const p = { label, kind, runHandler, isDefault }; this.profiles.push(p); return p; },
  createTestRun: (request) => new TestRun(request),
  dispose() {},
};
const diagStore = new Map();
const diags = { set: (uri, list) => diagStore.set(uri.toString(), list), delete: (uri) => diagStore.delete(uri.toString()), dispose() {} };
const commands = {};
const messages = { error: [], info: [] };
const disposable = () => ({ dispose() {} });
const LANG_OF = { ".py": "python", ".c": "c", ".cpp": "cpp", ".java": "java", ".js": "javascript", ".rs": "rust", ".rb": "ruby" };
const doc = (file) => ({
  languageId: LANG_OF[path.extname(file)] || "plaintext",
  uri: Uri.file(file), isDirty: false,
  getText: () => fs.readFileSync(file, "utf8"), save: async () => true,
});
const vscodeStub = {
  Position, Range, Location, Diagnostic, TestMessage, Uri, TestRunRequest,
  CancellationTokenSource: class { constructor() { this.token = { isCancellationRequested: false }; } },
  DiagnosticSeverity: { Error: 0, Warning: 1, Information: 2, Hint: 3 },
  TestRunProfileKind: { Run: 1, Debug: 2, Coverage: 3 },
  tests: { createTestController: () => controller },
  languages: { createDiagnosticCollection: () => diags },
  window: {
    activeTextEditor: undefined,
    createOutputChannel: () => ({ appendLine() {}, dispose() {} }),
    showErrorMessage: (m) => messages.error.push(m),
    showInformationMessage: (m) => messages.info.push(m),
  },
  workspace: {
    textDocuments: [doc(path.join(SAMPLES, "number_format.py"))],
    workspaceFolders: [{ uri: Uri.file(ROOT) }],
    getWorkspaceFolder: () => ({ uri: Uri.file(ROOT) }),
    getConfiguration: () => ({ get: (key, dflt) => (settings[key] !== undefined ? settings[key] : dflt) }),
    findFiles: async () => fs.readdirSync(SAMPLES).filter((f) => f.endsWith(".py")).map((f) => Uri.file(path.join(SAMPLES, f))),
    onDidOpenTextDocument: disposable, onDidSaveTextDocument: disposable, onDidChangeTextDocument: disposable,
  },
  commands: { registerCommand: (id, fn) => { commands[id] = fn; return disposable(); }, executeCommand: async () => undefined },
  extensions: { getExtension: () => undefined },
};
const settings = { script: "", python: "", inputMarker: "", args: ["-t", "3"] };
const realResolve = Module._resolveFilename;
Module._resolveFilename = function (request, ...rest) { return request === "vscode" ? "vscode" : realResolve.call(this, request, ...rest); };
require.cache.vscode = { id: "vscode", filename: "vscode", loaded: true, exports: vscodeStub };

// ---------------------------------------------------------------- tests
const ext = require(path.join(HERE, "extension.js"));
const token = { isCancellationRequested: false };
const id = (file, n) => Uri.file(file).toString() + (n ? "#" + n : "");
const states = (run, file, ns) => ns.map((n) => run.states.get(id(file, n)));

(async () => {
  ext.activate({ subscriptions: [], extensionPath: HERE });
  const runHandler = controller.profiles[0].runHandler;

  // discovery from an already-open document: three examples, ranges on the header lines
  const nf = path.join(SAMPLES, "number_format.py");
  const file = controller.items.get(id(nf));
  assert(file, "file item created for the open document");
  assert.strictEqual(file.children.size, 3);
  assert.deepStrictEqual([1, 2, 3].map((n) => file.children.get(id(nf, n)).range.start.line), [4, 9, 14]);
  assert.strictEqual(file.children.get(id(nf, 2)).parent, file);

  // whole file: every example fails with a diff, squiggles on lines 8/13/18, one consistent-issue warning
  await runHandler(new TestRunRequest([file]), token);
  let run = runs.at(-1);
  assert(run.ended);
  assert.deepStrictEqual(states(run, nf, [1, 2, 3]), ["failed", "failed", "failed"]);
  const m = run.messages.get(id(nf, 1));
  assert.match(m.message, /number formatting/);
  assert.match(m.message, /Hint: .*2 decimal places/);
  assert.strictEqual(m.expectedOutput.split("\n").at(-1), "The average is 3.50");
  assert.strictEqual(m.actualOutput.split("\n").at(-1), "The average is 3.5");
  assert.strictEqual(m.location.range.line, 7);
  let d = diagStore.get(id(nf));
  const errs = d.filter((x) => x.severity === 0), infos = d.filter((x) => x.severity === 2), warns = d.filter((x) => x.severity === 1);
  assert.deepStrictEqual(errs.map((x) => x.range.start.line), [7, 12, 17]);
  assert.strictEqual(errs[0].message, 'Example 1: number formatting: want "The average is 3.50" got "The average is 3.5"');
  assert.strictEqual(infos.length, 3);
  assert.strictEqual(warns.length, 1);
  assert.match(warns[0].message, /Consistent issue across 3 examples: number formatting/);
  assert.match(run.output, /Consistent issue: number formatting/);

  // one example: only that one gets a state
  await runHandler(new TestRunRequest([file.children.get(id(nf, 2))]), token);
  run = runs.at(-1);
  assert.deepStrictEqual(states(run, nf, [1, 2, 3]), [undefined, "failed", undefined]);

  // exclude
  await runHandler(new TestRunRequest([file], [file.children.get(id(nf, 3))]), token);
  run = runs.at(-1);
  assert.deepStrictEqual(states(run, nf, [1, 2, 3]), ["failed", "failed", undefined]);

  // the "test current file" command on a passing program: green, no squiggles
  const ok = path.join(SAMPLES, "passes.py");
  vscodeStub.window.activeTextEditor = { document: doc(ok) };
  await commands["autotester.testFile"]();
  run = runs.at(-1);
  assert.deepStrictEqual(states(run, ok, [1, 2]), ["passed", "passed"]);
  assert.deepStrictEqual(diagStore.get(id(ok)), []);

  // a file that cannot be parsed: errored, one diagnostic on the bad line
  const bad = path.join(SAMPLES, "syntax_error.py");
  vscodeStub.window.activeTextEditor = { document: doc(bad) };
  await commands["autotester.testFile"]();
  run = runs.at(-1);
  assert.deepStrictEqual(states(run, bad, [1]), ["errored"]);
  assert.match(run.messages.get(id(bad, 1)).message, /cannot parse file/);
  assert.deepStrictEqual(diagStore.get(id(bad)).map((x) => [x.range.start.line, x.severity]), [[8, 0]]);

  // a crash puts its squiggle on the program line, not in the docstring
  const crash = path.join(SAMPLES, "crash.py");
  vscodeStub.window.activeTextEditor = { document: doc(crash) };
  await commands["autotester.testFile"]();
  run = runs.at(-1);
  assert.deepStrictEqual(states(run, crash, [1, 2]), ["passed", "failed"]);
  d = diagStore.get(id(crash));
  assert.deepStrictEqual(d.filter((x) => x.severity === 0).map((x) => x.range.start.line), [21]);
  assert.match(d[0].message, /ZeroDivisionError/);

  // an unsupported editor is refused politely
  vscodeStub.window.activeTextEditor = { document: { languageId: "markdown" } };
  await commands["autotester.testFile"]();
  assert.match(messages.info.at(-1), /Open a Python, C, C\+\+, Java/);

  // C: the same diagnosis engine, and the hint names the printf line
  const cfmt = path.join(LANGS, "number_format.c");
  vscodeStub.window.activeTextEditor = { document: doc(cfmt) };
  await commands["autotester.testFile"]();
  run = runs.at(-1);
  assert.deepStrictEqual(states(run, cfmt, [1, 2]), ["failed", "failed"]);
  assert.match(run.messages.get(id(cfmt, 1)).message, /prints %\.1f.*2 decimal places.*%\.2f/);
  assert(diagStore.get(id(cfmt)).some((x) => x.severity === 0 && /number formatting/.test(x.message)));

  // a C program that does not compile: errored, with the compiler's own line and message
  const cbad = path.join(LANGS, "build_error.c");
  vscodeStub.window.activeTextEditor = { document: doc(cbad) };
  await commands["autotester.testFile"]();
  run = runs.at(-1);
  assert.deepStrictEqual(states(run, cbad, [1]), ["errored"]);
  assert.match(run.messages.get(id(cbad, 1)).message, /build failed/);
  d = diagStore.get(id(cbad)).filter((x) => x.severity === 0);
  assert.strictEqual(d.length, 1);
  assert.strictEqual(d[0].range.start.line, 9);
  assert.match(d[0].message, /expected ';'/);

  // Java runs too
  const java = path.join(LANGS, "Greeter.java");
  vscodeStub.window.activeTextEditor = { document: doc(java) };
  await commands["autotester.testFile"]();
  assert.deepStrictEqual(states(runs.at(-1), java, [1, 2]), ["failed", "failed"]);

  // the ": " marker, driven by the extension setting; the colliding output lines survive
  settings.inputMarker = ": ";
  const amb = path.join(COLON, "ambiguous.c");
  vscodeStub.window.activeTextEditor = { document: doc(amb) };
  await commands["autotester.testFile"]();
  run = runs.at(-1);
  assert.deepStrictEqual(states(run, amb, [1, 2]), ["failed", "failed"]);
  assert.strictEqual(diagStore.get(id(amb)).filter((x) => x.severity === 0).length, 2,
    "only the Speed line is wrong: Distance must not be read as input");
  assert.match(run.messages.get(id(amb, 1)).message, /number formatting/);

  const lab = path.join(COLON, "InLab02.c");
  vscodeStub.window.activeTextEditor = { document: doc(lab) };
  await commands["autotester.testFile"]();
  assert.deepStrictEqual(states(runs.at(-1), lab, [1, 2]), ["passed", "passed"]);
  settings.inputMarker = "";

  // workspace discovery finds every sample, and "test workspace" runs them all to a final state
  await controller.resolveHandler();
  const discovered = new Set();
  controller.items.forEach((i) => discovered.add(i.id));
  for (const f of fs.readdirSync(SAMPLES).filter((f) => f.endsWith(".py"))) {
    assert(discovered.has(id(path.join(SAMPLES, f))), `not discovered: ${f}`);
  }
  await commands["autotester.testWorkspace"]();
  run = runs.at(-1);
  const tally = {};
  for (const st of run.states.values()) tally[st] = (tally[st] || 0) + 1;
  console.log("workspace run:", tally);
  assert.strictEqual(tally.started, undefined, "every started example got a final state");
  assert(tally.passed >= 5, "passes.py x2, crash.py x1, rounding.py x2 at least");
  assert(tally.failed > 0 && tally.errored > 0);

  console.log(`ok: ${runs.length} runs, all assertions passed`);
})().catch((e) => { console.error(e); process.exit(1); });
