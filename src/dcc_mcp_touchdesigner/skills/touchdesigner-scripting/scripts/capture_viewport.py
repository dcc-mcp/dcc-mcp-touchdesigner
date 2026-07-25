"""Capture a screenshot of the current TouchDesigner viewport or a specific panel.

Args:
    panel_path: Optional path to a TOP or panel to capture. Defaults to main perform view.

Returns:
    dict with a base64-encoded PNG screenshot.
"""

from __future__ import annotations

import base64
import tempfile
from typing import Any, Optional

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_success


@skill_entry
def capture_viewport(panel_path: Optional[str] = None) -> dict[str, Any]:
    import td

    screenshot_path = None
    try:
        # Use TouchDesigner's built-in screenshot capability
        # If a specific panel_path is provided, target that TOP
        top = None
        if panel_path:
            try:
                top = td.op(panel_path)
            except Exception:
                pass

        # Write a temporary screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            screenshot_path = tmp.name

        if top is not None and hasattr(top, "save"):
            top.save(screenshot_path)
        else:
            # Fall back to op('perform') if available, otherwise save root
            try:
                perform = td.op("perform")
                if perform is not None and hasattr(perform, "save"):
                    perform.save(screenshot_path)
                else:
                    return skill_error("No suitable viewport TOP found for screenshot")
            except Exception:
                return skill_error("Failed to capture viewport screenshot")

        # Read back as base64
        with open(screenshot_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("ascii")

        return skill_success(
            {
                "format": "png",
                "encoding": "base64",
                "data": img_data,
            }
        )
    except Exception as exc:
        return skill_error(f"Screenshot failed: {exc}")
    finally:
        if screenshot_path:
            import os

            try:
                os.unlink(screenshot_path)
            except OSError:
                pass
