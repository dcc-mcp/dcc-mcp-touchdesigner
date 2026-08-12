"""Assemble dcc-mcp-touchdesigner release payload.

Usage: python packaging/assemble_release.py

Produces a zip archive with the wheel plus a bootstrap script that can be
extracted into TouchDesigner's site-packages or a custom project folder.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BOOTSTRAP_TEMPLATE = '''"""TouchDesigner MCP bootstrap — run from a Text DAT on the host thread."""
import os
import sys

_WHEEL = os.path.join(os.path.dirname(__file__), "payload", {wheel_name!r})
if not os.path.isfile(_WHEEL):
    raise RuntimeError(f"TouchDesigner adapter wheel not found: {{_WHEEL}}")
if _WHEEL not in sys.path:
    sys.path.insert(0, _WHEEL)

import dcc_mcp_touchdesigner

server = dcc_mcp_touchdesigner.start_server()
print(f"[dcc-mcp-touchdesigner] MCP server listening at {{server.mcp_url}}")
'''


def build_wheel() -> Path:
    """Build the Python wheel and return its path."""
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(DIST), str(ROOT)],
        check=True,
    )
    wheels = sorted(DIST.glob("dcc_mcp_touchdesigner-*.whl"))
    if not wheels:
        raise SystemExit("wheel build failed: no .whl found")
    return wheels[-1]


def assemble_zip(out_path: Path, wheel: Path) -> None:
    """Create the release zip with bootstrap script + wheel."""
    with ZipFile(out_path, "w", ZIP_DEFLATED) as zf:
        zf.writestr("bootstrap.py", BOOTSTRAP_TEMPLATE.format(wheel_name=wheel.name))
        zf.write(wheel, f"payload/{wheel.name}")
    print(f"Release zip written to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble dcc-mcp-touchdesigner release")
    parser.add_argument("-o", "--output", default=None, help="Output zip path")
    args = parser.parse_args()

    DIST.mkdir(exist_ok=True)
    wheel = build_wheel()
    out = args.output or str(DIST / "dcc-mcp-touchdesigner-release.zip")
    assemble_zip(Path(out), wheel)
    print("Done.")


if __name__ == "__main__":
    main()
