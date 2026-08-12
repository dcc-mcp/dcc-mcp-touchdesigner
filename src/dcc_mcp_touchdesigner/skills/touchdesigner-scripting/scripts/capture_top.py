"""Export a TOP to a deterministic PNG artifact."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import capture_top as _capture_top


@skill_entry
def main(path: str, output_path: str, overwrite: bool = False) -> dict[str, Any]:
    try:
        artifact = _capture_top(path, output_path, overwrite=overwrite)
        return skill_success("TouchDesigner TOP captured.", artifact=artifact)
    except TouchDesignerOperationError as exc:
        return skill_error("TOP capture failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="TOP capture failed.", include_traceback=False)
