#!/usr/bin/env python3
"""Package the extension as autotester-<version>.vsix using nothing but Python, and optionally install it.

    python3 build_vsix.py             # build the .vsix next to this file
    python3 build_vsix.py --install   # build it, then run `code --install-extension` on it

The .vsix bundles a copy of ../../autotester.py so the extension works in any folder.
Rebuild (and reinstall) after changing autotester.py or the extension.
"""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "autotester.py"

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="{id}" Version="{version}" Publisher="{publisher}" />
    <DisplayName>{display}</DisplayName>
    <Description xml:space="preserve">{description}</Description>
    <Tags>python,testing,docstring</Tags>
    <Categories>Testing</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{engine}" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
      <Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value="" />
      <Property Id="Microsoft.VisualStudio.Services.GitHubFlavoredMarkdown" Value="true" />
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code" />
  </Installation>
  <Dependencies />
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true" />
  </Assets>
</PackageManifest>
"""

CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json" />
  <Default Extension=".vsixmanifest" ContentType="text/xml" />
  <Default Extension=".js" ContentType="application/javascript" />
  <Default Extension=".md" ContentType="text/markdown" />
  <Default Extension=".py" ContentType="text/x-python" />
</Types>
"""


def code_cli():
    home = Path.home()
    for c in [shutil.which("code"),
              "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
              home / "AppData/Local/Programs/Microsoft VS Code/bin/code.cmd",
              "/usr/share/code/bin/code", "/usr/bin/code"]:
        if c and Path(c).exists():
            return str(c)
    return None


def main():
    pkg = json.loads((HERE / "package.json").read_text(encoding="utf-8"))
    out = HERE / f"{pkg['name']}-{pkg['version']}.vsix"
    files = {
        "extension/package.json": HERE / "package.json",
        "extension/extension.js": HERE / "extension.js",
        "extension/README.md": HERE.parent / "README.md",
        "extension/autotester.py": SCRIPT,
    }
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        sys.exit("missing: " + ", ".join(missing))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("extension.vsixmanifest", MANIFEST.format(
            id=escape(pkg["name"]), version=escape(pkg["version"]), publisher=escape(pkg["publisher"]),
            display=escape(pkg["displayName"]), description=escape(pkg["description"]),
            engine=escape(pkg["engines"]["vscode"])))
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        for arc, src in files.items():
            z.write(src, arc)
    print(f"built {out}")
    if "--install" not in sys.argv:
        print("install it with:  python3 build_vsix.py --install")
        print("   or in VS Code:  Extensions panel > '...' menu > Install from VSIX...")
        return 0
    cli = code_cli()
    if not cli:
        sys.exit("VS Code's 'code' command was not found. In VS Code run the command "
                 "'Shell Command: Install code command in PATH', or use Extensions > ... > Install from VSIX.")
    subprocess.run([cli, "--install-extension", str(out), "--force"], check=True)
    print("installed. If VS Code is open, run 'Developer: Reload Window' to pick it up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
