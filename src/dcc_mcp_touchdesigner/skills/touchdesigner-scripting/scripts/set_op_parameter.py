"""Set a parameter value on an operator.

Args:
    path: Path to the operator (e.g. '/project1/constant1').
    parameter: Parameter name to set.
    value: Value to set. Type depends on the parameter.

Returns:
    dict confirming the set operation.
"""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, set_operator_parameter


@skill_entry
def main(path: str, parameter: str, value: Any) -> dict[str, Any]:
    try:
        update = set_operator_parameter(path, parameter, value)
        return skill_success("TouchDesigner parameter updated.", update=update)
    except TouchDesignerOperationError as exc:
        return skill_error("Parameter update failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Parameter update failed.", include_traceback=False)
