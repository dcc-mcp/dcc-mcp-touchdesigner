"""Inspect one TouchDesigner operator through a bounded typed contract."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import inspect_operator as _inspect_operator


@skill_entry
def main(path: str) -> dict[str, Any]:
    try:
        return skill_success("TouchDesigner operator inspected.", inspection=_inspect_operator(path))
    except TouchDesignerOperationError as exc:
        return skill_error("Operator inspection failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Operator inspection failed.", include_traceback=False)
