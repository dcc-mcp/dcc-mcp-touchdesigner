# dcc-mcp-touchdesigner

TouchDesigner integration for the [DCC Model Context Protocol (MCP)](https://github.com/dcc-mcp/dcc-mcp-core) ecosystem.

Embeds a Streamable HTTP MCP server directly inside TouchDesigner, enabling AI
agents to execute Python, inspect operators, read/write parameters, and capture
screenshots — all through typed MCP tools dispatched on TouchDesigner's main
thread.

## Quick Start

Inside TouchDesigner's Python console or a DAT `execute` callback:

```python
import dcc_mcp_touchdesigner

# Start the server (OS-assigned port, gateway discovery)
server = dcc_mcp_touchdesigner.start_server()

# Discover skills
n = server.discover_skills()

# Load the scripting skill
server.load_skill("touchdesigner-scripting")

# The server is now listening — connect from Claude Desktop or gateway
print(server.mcp_url)
```

## Installation

```bash
pip install dcc-mcp-touchdesigner
```

Then inside TouchDesigner, ensure `dcc-mcp-core` and `dcc-mcp-touchdesigner`
are available in `sys.path`.

See [install.md](install.md) for detailed setup instructions.

## Skills

- **touchdesigner-scripting** — execute Python, list operators, read/write parameters, capture viewport

## Capability Matrix

| Capability         | Supported | Notes                                    |
|--------------------|-----------|------------------------------------------|
| Scene Manager      | ✅        | Operator hierarchy via `td.op()`          |
| Transform          | ✅        | Parameter value read/write               |
| Hierarchy          | ✅        | Component children traversal             |
| Render/Capture     | ✅        | TOP save to PNG, base64 output            |
| Selection          | ✅        | Via `td.op()` path resolution            |
| Snapshot           | ✅        | `capture_viewport` tool                  |
| Undo/Redo          | ❌        | TouchDesigner has limited undo support   |
| File Operations    | ✅        | `.toe` / `.tox` load/save via Python      |
| Embedded Python    | ✅        | `td` module always available             |
| Progress Reporting | ❌        | Not yet implemented                      |
| Scene Info         | ✅        | `get_project_info` tool                  |

## Environment Variables

| Variable                                       | Purpose                                    |
|------------------------------------------------|--------------------------------------------|
| `DCC_MCP_TOUCHDESIGNER_SKILL_PATHS`            | Extra skill directories                    |
| `DCC_MCP_TOUCHDESIGNER_METRICS`                | Enable Prometheus `/metrics`               |
| `DCC_MCP_TOUCHDESIGNER_ENABLE_GATEWAY_FAILOVER`| Gateway failover (default: enabled)        |
| `DCC_MCP_TOUCHDESIGNER_DISABLE_EXECUTE_PYTHON` | Disable `execute_python` tool              |

## License

MIT
