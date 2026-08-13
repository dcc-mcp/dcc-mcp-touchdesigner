"""Atomically update explicit TouchDesigner root timeline fields."""

from __future__ import annotations

from typing import Any, Optional

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import set_timeline_state as _set_timeline_state


@skill_entry
def main(
    frame: Optional[float] = None,
    play: Optional[bool] = None,
    cook_rate: Optional[float] = None,
    real_time: Optional[bool] = None,
) -> dict[str, Any]:
    try:
        update = _set_timeline_state(frame=frame, play=play, cook_rate=cook_rate, real_time=real_time)
        return skill_success("TouchDesigner timeline updated.", update=update)
    except TouchDesignerOperationError as exc:
        return skill_error("Timeline update failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Timeline update failed.", include_traceback=False)
