"""Pulse one explicit TouchDesigner parameter."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, pulse_operator_parameter


@skill_entry
def main(
    path: str,
    parameter: str,
    value: Any = 1,
    frames: int = 0,
    seconds: float = 0.0,
) -> dict[str, Any]:
    try:
        pulse = pulse_operator_parameter(path, parameter, value=value, frames=frames, seconds=seconds)
        return skill_success("TouchDesigner parameter pulsed.", pulse=pulse)
    except TouchDesignerOperationError as exc:
        return skill_error("Parameter pulse failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Parameter pulse failed.", include_traceback=False)
