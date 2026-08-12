"""Return basic information about the current TouchDesigner project.

Returns:
    dict with project name, fps, resolution, python version, and td version.
"""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import get_project_info as _get_project_info


@skill_entry
def main() -> dict[str, Any]:
    try:
        return skill_success("TouchDesigner project inspected.", project=_get_project_info())
    except Exception as exc:
        return skill_exception(exc, message="Project inspection failed.", include_traceback=False)
