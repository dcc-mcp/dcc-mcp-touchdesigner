"""Save the current TouchDesigner project to an explicit .toe path."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import save_project as _save_project


@skill_entry
def main(path: str, overwrite: bool = False) -> dict[str, Any]:
    try:
        artifact = _save_project(path, overwrite=overwrite)
        return skill_success("TouchDesigner project saved.", artifact=artifact)
    except TouchDesignerOperationError as exc:
        return skill_error("Project save failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Project save failed.", include_traceback=False)
