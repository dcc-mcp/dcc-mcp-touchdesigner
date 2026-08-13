"""Inspect connector topology for one TouchDesigner operator."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import inspect_connections as _inspect_connections


@skill_entry
def main(path: str) -> dict[str, Any]:
    try:
        return skill_success("TouchDesigner connections inspected.", topology=_inspect_connections(path))
    except TouchDesignerOperationError as exc:
        return skill_error("Connection inspection failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Connection inspection failed.", include_traceback=False)
