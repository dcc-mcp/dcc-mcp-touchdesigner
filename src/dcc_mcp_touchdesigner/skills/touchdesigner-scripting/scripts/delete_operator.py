"""Delete one non-root TouchDesigner operator."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import delete_operator as _delete_operator


@skill_entry
def main(path: str) -> dict[str, Any]:
    try:
        deleted = _delete_operator(path)
        return skill_success("TouchDesigner operator deleted.", deleted=deleted)
    except TouchDesignerOperationError as exc:
        return skill_error("Operator deletion failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Operator deletion failed.", include_traceback=False)
