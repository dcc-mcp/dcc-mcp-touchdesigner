"""Get parameter values of a specific operator.

Args:
    path: Path to the operator (e.g. '/project1/constant1').

Returns:
    dict with parameter information.
"""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_success


@skill_entry
def get_op_parameters(path: str) -> dict[str, Any]:
    import td

    try:
        op = td.op(path)
    except Exception:
        return skill_error(f"Failed to resolve operator at path: {path}")

    if op is None:
        return skill_error(f"Operator not found at path: {path}")

    params: dict[str, Any] = {}
    for par in op.pars():
        name = par.name
        try:
            val = par.eval()
            params[name] = {
                "value": val,
                "label": par.label,
                "default": getattr(par, "default", None),
                "mode": str(getattr(par, "mode", "CONSTANT")),
            }
        except Exception:
            params[name] = {
                "value": str(par),
                "label": par.label,
                "mode": str(getattr(par, "mode", "CONSTANT")),
            }

    return skill_success(
        {
            "path": path,
            "name": op.name,
            "type": str(op.type) if hasattr(op, "type") else str(type(op)),
            "parameter_count": len(params),
            "parameters": params,
        }
    )
