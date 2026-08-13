"""Atomically update allowlisted TouchDesigner operator flags."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import set_operator_flags as _set_operator_flags


@skill_entry
def main(path: str, flags: dict[str, bool]) -> dict[str, Any]:
    try:
        return skill_success("TouchDesigner operator flags updated.", update=_set_operator_flags(path, flags))
    except TouchDesignerOperationError as exc:
        return skill_error("Operator flag update failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Operator flag update failed.", include_traceback=False)
