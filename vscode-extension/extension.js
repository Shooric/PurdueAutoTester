// Autotester for VS Code.
//
// Runs the "Example execution N" transcripts in a program's docstring or header comment
// by calling autotester.py --json, and shows the results three ways: in the Test Explorer
// (one test per example, run buttons in the gutter next to each header), as squiggles under
// the example lines that differ from what the program printed, and as a diff view when a
// failed example is clicked.  Plain JavaScript, no build step.
//
// Python, C, C++, Java, JavaScript, Rust and Ruby; compilers are run for you, and their
// errors and warnings show up in the Problems panel alongside the example failures.
"use strict";
const vscode = require("vscode");
const cp = require("child_process");
const fs = require("fs");
const path = require("path");

// Keep in sync with HEADER_RE in autotester.py.
const HEADER = /^[ \t]*Example[ \t]+execution[ \t]*#?[ \t]*(\d+)\b/i;
const SKIP = "**/{.git,.venv,venv,env,__pycache__,node_modules,.idea,.vscode}/**";
const STRUCTURAL = new Set(["crash", "timeout", "input"]);
// Keep in sync with LANGUAGES in autotester.py.
const LANGS = new Set(["python", "c", "cpp", "java", "javascript", "rust", "ruby"]);
const GLOB = "**/*.{py,c,cpp,cc,cxx,c++,java,js,mjs,rs,rb}";

function activate(context) {
  const ctrl = vscode.tests.createTestController("autotester", "Docstring examples");
  const diags = vscode.languages.createDiagnosticCollection("autotester");
  const out = vscode.window.createOutputChannel("Autotester");
  context.subscriptions.push(ctrl, diags, out);
  const signatures = new Map(); // uri -> "n:line,n:line" so unchanged files keep their test state

  // ---------------------------------------------------------------- discovery
  function discoverText(uri, text) {
    const found = [];
    text.split(/\r?\n/).forEach((ln, i) => {
      const m = HEADER.exec(ln);
      if (m) found.push({ n: Number(m[1]), line: i, len: ln.length });
    });
    const id = uri.toString();
    if (!found.length) {
      ctrl.items.delete(id);
      signatures.delete(id);
      return null;
    }
    const signature = found.map((f) => `${f.n}:${f.line}`).join(",");
    let file = ctrl.items.get(id);
    if (file && signatures.get(id) === signature) return file;
    if (!file) {
      file = ctrl.createTestItem(id, path.basename(uri.fsPath), uri);
      ctrl.items.add(file);
    }
    file.children.replace(found.map(({ n, line, len }) => {
      const t = ctrl.createTestItem(`${id}#${n}`, `Example ${n}`, uri);
      t.range = new vscode.Range(line, 0, line, len);
      t.sortText = String(n).padStart(4, "0");
      return t;
    }));
    signatures.set(id, signature);
    return file;
  }

  function discoverDocument(doc) {
    if (!LANGS.has(doc.languageId) || doc.uri.scheme !== "file") return null;
    if (path.basename(doc.uri.fsPath) === "autotester.py") return null;
    return discoverText(doc.uri, doc.getText());
  }

  async function discoverWorkspace() {
    const uris = await vscode.workspace.findFiles(GLOB, SKIP);
    for (const uri of uris) {
      if (path.basename(uri.fsPath) === "autotester.py") continue;
      try {
        discoverText(uri, fs.readFileSync(uri.fsPath, "utf8"));
      } catch (e) {
        /* unreadable file: skip it */
      }
    }
  }

  ctrl.resolveHandler = async (item) => {
    if (!item) await discoverWorkspace();
  };
  vscode.workspace.textDocuments.forEach(discoverDocument);
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument(discoverDocument),
    vscode.workspace.onDidSaveTextDocument(discoverDocument),
    vscode.workspace.onDidChangeTextDocument((e) => {
      discoverDocument(e.document);
      diags.delete(e.document.uri); // squiggles from the last run are stale once the file changes
    }),
  );

  // ---------------------------------------------------------------- settings
  const cfg = () => vscode.workspace.getConfiguration("autotester");

  function findScript() {
    const folders = (vscode.workspace.workspaceFolders || []).map((f) => f.uri.fsPath);
    const candidates = [
      cfg().get("script"),
      path.join(context.extensionPath, "autotester.py"),
      path.join(context.extensionPath, "..", "autotester.py"),
      ...folders.map((f) => path.join(f, "autotester.py")),
    ].filter(Boolean);
    return candidates.find((p) => fs.existsSync(p));
  }

  async function findPython(resource) {
    const setting = cfg().get("python");
    if (setting) return setting;
    try {
      const ext = vscode.extensions.getExtension("ms-python.python");
      if (ext) {
        const api = ext.isActive ? ext.exports : await ext.activate();
        const envs = api && api.environments;
        if (envs) {
          const active = envs.getActiveEnvironmentPath(resource);
          const resolved = await envs.resolveEnvironment(active);
          if (resolved && resolved.executable && resolved.executable.uri) return resolved.executable.uri.fsPath;
          if (active && active.path) return active.path;
        }
      }
    } catch (e) {
      /* no Python extension: fall through */
    }
    return process.platform === "win32" ? "python" : "python3";
  }

  // ---------------------------------------------------------------- running
  function runTester(python, script, file, numbers, cwd) {
    const marker = cfg().get("inputMarker");
    const args = [script, file, "--json"];
    if (marker) args.push("--input-marker", marker);
    args.push(...cfg().get("args", []));
    if (numbers) args.push("-e", ...numbers.map(String));
    out.appendLine(`$ ${[python, ...args].map((a) => (/\s/.test(a) ? JSON.stringify(a) : a)).join(" ")}`);
    return new Promise((resolve) => {
      cp.execFile(python, args, { cwd, maxBuffer: 64 * 1024 * 1024 }, (err, stdout, stderr) => {
        if (stderr) out.appendLine(stderr);
        try {
          resolve({ data: JSON.parse(stdout) }); // exit code 1 just means something failed
        } catch (e) {
          const why = err && err.code === "ENOENT"
            ? `cannot run "${python}": is Python installed? (set autotester.python)`
            : `autotester.py did not return JSON:\n${stderr || stdout || (err && err.message) || ""}`;
          resolve({ error: why });
        }
      });
    });
  }

  function applyFile(run, file, f, targets) {
    const uri = file.uri;
    const list = [];
    const D = vscode.DiagnosticSeverity;
    const diag = (line, message, severity) => {
      const l = Math.max(0, (line || 1) - 1);
      const d = new vscode.Diagnostic(new vscode.Range(l, 0, l, 1000), message, severity);
      d.source = "autotester";
      list.push(d);
    };
    const lines = [];
    for (const w of f.warnings || []) {
      diag(w.line, w.message, D.Warning);
      lines.push(`warning: line ${w.line}: ${w.message}`);
    }
    if (f.error) {
      const detail = (f.diagnostics || []).map((x) => `line ${x.line}: ${x.message}`).join("\n");
      if ((f.diagnostics || []).length) {
        for (const x of f.diagnostics) diag(x.line, x.message, D.Error);
      } else {
        diag(f.error_line, f.error, D.Error);
      }
      const msg = detail ? `${f.error}\n${detail}` : f.error;
      targets.forEach((t) => run.errored(t, new vscode.TestMessage(msg)));
      lines.push(f.error, ...detail.split("\n").filter(Boolean));
    } else {
      const seen = new Set();
      for (const ex of f.examples || []) {
        const item = file.children.get(`${uri.toString()}#${ex.number}`);
        if (!item || !targets.has(item)) continue;
        seen.add(item);
        if (ex.passed) {
          run.passed(item);
          continue;
        }
        const msg = vscode.TestMessage.diff(`${ex.detail}\nHint: ${ex.hint}`,
          ex.expected.join("\n"), ex.actual.join("\n"));
        const at = (ex.issues[0] && ex.issues[0].line) || ex.line;
        msg.location = new vscode.Location(uri, new vscode.Position(Math.max(0, at - 1), 0));
        run.failed(item, msg);
        lines.push(`FAIL  Example ${ex.number}: ${ex.detail}`, `      hint: ${ex.hint}`);
        for (const i of ex.issues) {
          const text = STRUCTURAL.has(i.kind) ? i.detail
            : i.got == null ? `missing line: "${i.want}"`
            : i.want == null ? `extra line: "${i.got}"`
            : `${i.label}: want "${i.want}" got "${i.got}"`;
          diag(i.line, `Example ${ex.number}: ${text}`, D.Error);
        }
        diag(ex.line, `Example ${ex.number} failed: ${ex.detail}. Hint: ${ex.hint}`, D.Information);
      }
      targets.forEach((t) => { if (!seen.has(t)) run.skipped(t); });
      const s = f.summary;
      if (s && s.consistent && s.failing >= 2) {
        const first = f.examples.find((e) => !e.passed);
        const what = STRUCTURAL.has(s.kind) ? `${s.label}: ${s.detail}` : s.label;
        diag(first ? first.line : 1, `Consistent issue across ${s.examples} examples: ${what}. Hint: ${s.hint}`, D.Warning);
        lines.push(`Consistent issue: ${what}`, `      hint: ${s.hint}`);
      }
      lines.push(`${f.passed}/${f.total} passed`);
    }
    diags.set(uri, list);
    run.appendOutput(`== ${path.basename(uri.fsPath)}\r\n${lines.map((l) => "   " + l).join("\r\n")}\r\n`);
  }

  async function runHandler(request, token) {
    const run = ctrl.createTestRun(request);
    try {
      const script = findScript();
      if (!script) {
        const m = "autotester.py not found: put it in the workspace folder, or set autotester.script in Settings.";
        vscode.window.showErrorMessage(m);
        run.appendOutput(m + "\r\n");
        return;
      }
      let roots = request.include;
      if (!roots) {
        await discoverWorkspace();
        roots = [];
        ctrl.items.forEach((i) => roots.push(i));
      }
      const excluded = new Set(request.exclude || []);
      const byFile = new Map(); // file item -> Set of example items, or null for "all of them"
      for (const item of roots) {
        if (excluded.has(item)) continue;
        const file = item.parent || item;
        if (!byFile.has(file)) byFile.set(file, item.parent ? new Set() : null);
        if (item.parent && byFile.get(file)) byFile.get(file).add(item);
      }
      for (const [file, subset] of byFile) {
        if (token.isCancellationRequested) break;
        const targets = new Set();
        file.children.forEach((c) => { if ((!subset || subset.has(c)) && !excluded.has(c)) targets.add(c); });
        if (!targets.size) continue;
        targets.forEach((t) => run.started(t));
        const numbers = subset ? [...targets].map((t) => Number(t.id.split("#").pop())) : null;
        const folder = vscode.workspace.getWorkspaceFolder(file.uri);
        const cwd = folder ? folder.uri.fsPath : path.dirname(file.uri.fsPath);
        const res = await runTester(await findPython(file.uri), script, file.uri.fsPath, numbers, cwd);
        if (res.error) {
          targets.forEach((t) => run.errored(t, new vscode.TestMessage(res.error)));
          run.appendOutput(res.error.replace(/\n/g, "\r\n") + "\r\n");
          continue;
        }
        const f = res.data.files && res.data.files[0];
        if (!f) {
          targets.forEach((t) => run.skipped(t));
          continue;
        }
        applyFile(run, file, f, targets);
      }
    } finally {
      run.end();
    }
  }

  ctrl.createRunProfile("Run examples", vscode.TestRunProfileKind.Run, runHandler, true);

  // ---------------------------------------------------------------- commands
  const fresh = () => new vscode.CancellationTokenSource().token;
  context.subscriptions.push(
    vscode.commands.registerCommand("autotester.testFile", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || !LANGS.has(editor.document.languageId)) {
        vscode.window.showInformationMessage(
          "Open a Python, C, C++, Java, JavaScript, Rust or Ruby file first.");
        return;
      }
      if (editor.document.isDirty) await editor.document.save();
      const file = discoverDocument(editor.document);
      if (!file) {
        vscode.window.showInformationMessage(
          "No \"Example execution N\" blocks in this file's docstring or comments.");
        return;
      }
      await runHandler(new vscode.TestRunRequest([file]), fresh());
    }),
    vscode.commands.registerCommand("autotester.testWorkspace", async () => {
      await discoverWorkspace();
      await runHandler(new vscode.TestRunRequest(), fresh());
    }),
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
