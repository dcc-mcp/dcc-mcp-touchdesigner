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

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import list_operators as _list_operators


@skill_entry
def main(
    path: str = "/",
    recurse: bool = False,
    type_filter: Optional[str] = None,
    limit: int = 500,
) -> dict[str, Any]:
    try:
        listing = _list_operators(path or "/", recurse=recurse, type_filter=type_filter, limit=limit)
        return skill_success("TouchDesigner operators listed.", listing=listing)
    except TouchDesignerOperationError as exc:
        return skill_error("Operator listing failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Operator listing failed.", include_traceback=False)
