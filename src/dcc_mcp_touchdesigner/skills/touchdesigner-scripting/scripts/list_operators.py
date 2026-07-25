"""List operators in a given component or the root.

Args:
    path: Path to a COMP to list children of (e.g. '/project1'). Defaults to root '/'.
    recurse: If true, recurse into child components.
    type_filter: Optional operator type filter (e.g. 'COMP', 'TOP', 'CHOP', 'SOP', 'MAT', 'DAT').

Returns:
    dict with a list of operators.
"""

from __future__ import annotations

from typing import Any, Optional

from dcc_mcp_touchdesigner.api import skill_entry, skill_success


def _list_children(op_path: str, recurse: bool, type_filter: Optional[str]) -> list[dict[str, Any]]:
    import td

    try:
        parent = td.op(op_path)
    except Exception:
        return []

    if parent is None:
        return []

    results: list[dict[str, Any]] = []
    for child in parent.children:
        child_type = child.type if hasattr(child, "type") else str(type(child))
        if type_filter and child_type != type_filter:
            if recurse and hasattr(child, "children") and child.children:
                results.extend(_list_children(str(child), recurse, type_filter))
            continue

        results.append(
            {
                "name": child.name,
                "path": str(child),
                "type": child_type,
                "label": getattr(child, "label", ""),
            }
        )

        if recurse and hasattr(child, "children") and child.children:
            results.extend(_list_children(str(child), recurse, type_filter))

    return results


@skill_entry
def list_operators(
    path: str = "/",
    recurse: bool = False,
    type_filter: Optional[str] = None,
) -> dict[str, Any]:
    if not path:
        path = "/"

    ops = _list_children(path, recurse, type_filter)
    return skill_success(
        {
            "path": path,
            "count": len(ops),
            "operators": ops,
        }
    )
