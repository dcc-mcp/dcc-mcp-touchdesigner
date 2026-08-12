"""Get parameter values of a specific operator.

Args:
    path: Path to the operator (e.g. '/project1/constant1').

Returns:
    dict with parameter information.
"""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import (
    TouchDesignerOperationError,
    get_operator_parameters,
)


@skill_entry
def main(path: str, names: list[str] | None = None) -> dict[str, Any]:
    try:
        parameters = get_operator_parameters(path, names=names)
        return skill_success("TouchDesigner parameters inspected.", parameters=parameters)
    except TouchDesignerOperationError as exc:
        return skill_error("Parameter inspection failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Parameter inspection failed.", include_traceback=False)
