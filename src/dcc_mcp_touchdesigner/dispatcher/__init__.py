"""TouchDesigner dispatcher compatibility exports backed by dcc-mcp-core."""

from __future__ import annotations

from dcc_mcp_touchdesigner.host import (
    TouchDesignerCallableDispatcher,
    TouchDesignerInlineCallableDispatcher,
    TouchDesignerTimerPump,
    TouchDesignerUiDispatcher,
)

__all__ = [
    "TouchDesignerUiDispatcher",
    "TouchDesignerCallableDispatcher",
    "TouchDesignerInlineCallableDispatcher",
    "TouchDesignerTimerPump",
]
