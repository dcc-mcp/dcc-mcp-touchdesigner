"""Replace one Text/Table DAT with optimistic concurrency."""

from __future__ import annotations

from typing import Any, Optional

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError
from dcc_mcp_touchdesigner.operations import set_dat_content as _set_dat_content


@skill_entry
def main(path: str, content: str, expected_sha256: Optional[str] = None) -> dict[str, Any]:
    try:
        update = _set_dat_content(path, content, expected_sha256=expected_sha256)
        return skill_success("TouchDesigner DAT content updated.", update=update)
    except TouchDesignerOperationError as exc:
        return skill_error("DAT content update failed.", str(exc))
    except Exception as exc:
        return skill_exception(exc, message="DAT content update failed.", include_traceback=False)
