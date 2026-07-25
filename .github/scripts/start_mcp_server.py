"""CI script — start the TouchDesigner MCP server for smoke testing.

This script CANNOT run in CI without a running TouchDesigner process.
It serves as a reference for manual smoke testing.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    """Start dcc-mcp-touchdesigner and print the MCP URL as JSON."""
    try:
        import dcc_mcp_touchdesigner
    except ImportError:
        print(json.dumps({"error": "dcc_mcp_touchdesigner not installed"}))
        return 1

    try:
        server = dcc_mcp_touchdesigner.start_server(port=0)
        server.discover_skills()
        print(json.dumps({
            "status": "running",
            "mcp_url": server.mcp_url,
            "port": server.port,
            "version": dcc_mcp_touchdesigner.__version__,
            "skills_discovered": server.loaded_skill_count(),
        }))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
