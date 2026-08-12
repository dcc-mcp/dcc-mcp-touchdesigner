"""Wire two TouchDesigner operators through explicit connector indices."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import connect_operators as _connect_operators


@skill_entry
def main(
    source_path: str,
    target_path: str,
    output_index: int = 0,
    input_index: int = 0,
) -> dict[str, Any]:
    try:
        connection = _connect_operators(
            source_path,
            target_path,
            output_index=output_index,
            input_index=input_index,
        )
        return skill_success("TouchDesigner operators connected.", connection=connection)
    except TouchDesignerOperationError as exc:
        return skill_error("Operator connection failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="Operator connection failed.", include_traceback=False)
