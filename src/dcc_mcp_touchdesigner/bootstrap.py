"""Shared release and installed TouchDesigner bootstrap rendering."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_TEMPLATE_PATH = Path(__file__).resolve().parent / "resources" / "bootstrap.py.tmpl"


def render_bootstrap(adapter_path_expression: str) -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8").replace("{adapter_path}", adapter_path_expression)


def render_execute_dat(bootstrap_path: Path) -> str:
    bootstrap = repr(str(bootstrap_path.resolve(strict=False)))
    return (
        '"""DCC-MCP startup callbacks for a TouchDesigner Execute DAT."""\n'
        "\n"
        "def onStart():\n"
        "    import runpy\n"
        f"    runpy.run_path({bootstrap}, run_name='__dcc_mcp_touchdesigner_bootstrap__')\n"
        "    return\n"
        "\n"
        "\n"
        "def onExit():\n"
        "    import dcc_mcp_touchdesigner\n"
        "    dcc_mcp_touchdesigner.stop_server()\n"
        "    return\n"
    )


def bootstrap_error_path() -> Path:
    configured = os.environ.get("DCC_MCP_TOUCHDESIGNER_BOOTSTRAP_ERROR_LOG")
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    return Path.home() / ".dcc-mcp" / "logs" / "touchdesigner-bootstrap.jsonl"


def bootstrap_error_summary() -> dict[str, Any]:
    path = bootstrap_error_path()
    if not path.is_file():
        return {"path": str(path), "last": None, "records_read": 0}
    try:
        lines = path.read_bytes()[-262144:].splitlines()
    except OSError as exc:
        return {"path": str(path), "last": {"success": False, "reason": str(exc)}, "records_read": 0}
    records = []
    for line in lines:
        try:
            payload = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return {"path": str(path), "last": records[-1] if records else None, "records_read": len(records)}
