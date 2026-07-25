# Installing dcc-mcp-touchdesigner

## Prerequisites

- TouchDesigner 2023+ (commercial or non-commercial)
- Python 3.9+ (TouchDesigner's built-in Python)

## Installation Steps

### 1. Install the Python packages

```bash
pip install dcc-mcp-core dcc-mcp-touchdesigner
```

### 2. Verify in TouchDesigner

Open TouchDesigner, open the Textport (Alt+T), and run:

```python
import dcc_mcp_core
import dcc_mcp_touchdesigner
print(dcc_mcp_touchdesigner.__version__)
```

If any import fails, add the pip site-packages to `sys.path`:

```python
import sys
sys.path.insert(0, r"C:\path\to\site-packages")
```

### 3. Start the MCP server

```python
import dcc_mcp_touchdesigner
server = dcc_mcp_touchdesigner.start_server()
print(server.mcp_url)
```

### 4. Connect from Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "touchdesigner": {
      "url": "http://127.0.0.1:PORT/mcp"
    }
  }
}
```

Replace `PORT` with the port shown by `server.mcp_url`.

### Gateway Mode (multi-instance)

When a dcc-mcp gateway is running, the server auto-registers. Set:

```bash
export DCC_MCP_GATEWAY_PORT=9765
export DCC_MCP_REGISTRY_DIR=/tmp/dcc_registry
```

The gateway aggregates all TouchDesigner instances under one endpoint.

## Troubleshooting

- **ImportError: No module named 'dcc_mcp_core'**: Ensure `dcc-mcp-core` is installed in the same Python environment.
- **Connection refused**: TouchDesigner firewall may block the port. Use `localhost` only or allow the port.
- **`td` module not found**: The Python code must run inside TouchDesigner's process.
