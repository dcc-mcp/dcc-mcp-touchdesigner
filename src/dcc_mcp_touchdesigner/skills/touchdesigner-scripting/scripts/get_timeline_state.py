"""Inspect the TouchDesigner root timeline and project cooking state."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, get_timeline_state


@skill_entry
def main() -> dict[str, Any]:
    try:
        return skill_success("TouchDesigner timeline inspected.", timeline=get_timeline_state())
    except TouchDesignerOperationError as exc:
        return skill_error("Timeline inspection failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Timeline inspection failed.", include_traceback=False)
