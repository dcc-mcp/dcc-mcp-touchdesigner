"""Return basic information about the current TouchDesigner project.

Returns:
    dict with project name, fps, resolution, python version, and td version.
"""

from __future__ import annotations

import sys
from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_success


@skill_entry
def get_project_info() -> dict[str, Any]:
    import td

    project = td.mod(td.rootPage).name if hasattr(td, "rootPage") else "unknown"

    return skill_success(
        {
            "project_name": project,
            "touchdesigner_version": str(td.version),
            "python_version": sys.version,
            "fps": float(project.fps) if hasattr(project, "fps") else None,
        }
    )
