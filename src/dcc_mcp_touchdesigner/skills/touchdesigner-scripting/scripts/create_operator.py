"""Create a typed operator inside a TouchDesigner component."""

from __future__ import annotations

from typing import Any, Optional

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import create_operator as _create_operator


@skill_entry
def main(parent_path: str, operator_type: str, name: Optional[str] = None) -> dict[str, Any]:
    try:
        created = _create_operator(parent_path, operator_type, name=name)
        return skill_success("TouchDesigner operator created.", created=created)
    except TouchDesignerOperationError as exc:
        return skill_error("Operator creation failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Operator creation failed.", include_traceback=False)
