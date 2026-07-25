"""dcc-mcp-touchdesigner — MCP Streamable HTTP server embedded in TouchDesigner."""

# The compatibility gate must run before imports that bind core integrations.
# ruff: noqa: E402

from __future__ import annotations

from dcc_mcp_touchdesigner._core_compat import require_compatible_core

require_compatible_core()

from dcc_mcp_touchdesigner.__version__ import __version__
from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_exception, skill_success
from dcc_mcp_touchdesigner.capabilities import touchdesigner_capabilities, touchdesigner_capabilities_dict
from dcc_mcp_touchdesigner.host import (
    TouchDesignerHost,
    TouchDesignerTimerPump,
    TouchDesignerUiDispatcher,
)
from dcc_mcp_touchdesigner.server import (
    DEFAULT_PORT,
    SERVER_NAME,
    TouchDesignerMcpServer,
    TouchDesignerServerOptions,
    get_server,
    start_server,
    stop_server,
)

__all__ = [
    "__version__",
    "skill_entry",
    "skill_error",
    "skill_exception",
    "skill_success",
    "touchdesigner_capabilities",
    "touchdesigner_capabilities_dict",
    "TouchDesignerHost",
    "TouchDesignerTimerPump",
    "TouchDesignerUiDispatcher",
    "TouchDesignerMcpServer",
    "TouchDesignerServerOptions",
    "DEFAULT_PORT",
    "SERVER_NAME",
    "get_server",
    "start_server",
    "stop_server",
]
