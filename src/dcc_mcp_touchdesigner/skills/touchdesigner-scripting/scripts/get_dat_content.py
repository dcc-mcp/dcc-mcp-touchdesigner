"""Read bounded Unicode content from one TouchDesigner DAT."""

from __future__ import annotations

from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import get_dat_content as _get_dat_content


@skill_entry
def main(path: str, max_bytes: int = 1_048_576) -> dict[str, Any]:
    try:
        return skill_success(
            "TouchDesigner DAT content inspected.", document=_get_dat_content(path, max_bytes=max_bytes)
        )
    except TouchDesignerOperationError as exc:
        return skill_error("DAT content inspection failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="DAT content inspection failed.", include_traceback=False)
