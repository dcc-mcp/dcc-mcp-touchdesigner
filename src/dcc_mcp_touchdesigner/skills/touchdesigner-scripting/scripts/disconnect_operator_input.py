"""Disconnect one exact TouchDesigner input connector."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import disconnect_operator_input as _disconnect_operator_input


@skill_entry
def main(path: str, input_index: int = 0) -> dict[str, Any]:
    try:
        result = _disconnect_operator_input(path, input_index=input_index)
        return skill_success("TouchDesigner input disconnected.", disconnection=result)
    except TouchDesignerOperationError as exc:
        return skill_error("Input disconnection failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Input disconnection failed.", include_traceback=False)
