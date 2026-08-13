"""Atomically update bounded TouchDesigner Network Editor layout fields."""

from __future__ import annotations

from typing import Any, Optional

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import set_operator_layout as _set_operator_layout


@skill_entry
def main(
    path: str,
    x: Optional[int] = None,
    y: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> dict[str, Any]:
    try:
        return skill_success(
            "TouchDesigner operator layout updated.",
            update=_set_operator_layout(path, x=x, y=y, width=width, height=height),
        )
    except TouchDesignerOperationError as exc:
        return skill_error("Operator layout update failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Operator layout update failed.", include_traceback=False)
