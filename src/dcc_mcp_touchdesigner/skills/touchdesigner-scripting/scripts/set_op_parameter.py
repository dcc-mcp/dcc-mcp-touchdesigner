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

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_success


@skill_entry
def set_op_parameter(path: str, parameter: str, value: Any) -> dict[str, Any]:
    import td

    try:
        op = td.op(path)
    except Exception:
        return skill_error(f"Failed to resolve operator at path: {path}")

    if op is None:
        return skill_error(f"Operator not found at path: {path}")

    try:
        par_ref = op.par[parameter]
        par_ref.val = value
    except Exception as exc:
        return skill_error(f"Failed to set parameter '{parameter}' on '{path}': {exc}")

    # Read back to confirm
    new_val = par_ref.eval()
    return skill_success(
        {
            "path": path,
            "parameter": parameter,
            "value": new_val,
        }
    )
