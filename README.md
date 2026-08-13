# dcc-mcp-touchdesigner

<p align="center">
  <img src="docs/assets/dcc-mcp-touchdesigner.svg" alt="DCC-MCP · TouchDesigner" width="600">
</p>

Typed, main-thread-safe TouchDesigner control for the [DCC Model Context Protocol](https://github.com/dcc-mcp/dcc-mcp-core).

The adapter embeds the DCC-MCP HTTP runtime in TouchDesigner, registers the instance with the local gateway, and executes TouchDesigner API work through the documented `td.run()` scheduler. Agents can inspect and edit operator networks, parameters, Unicode DAT content, and root timeline state, then save projects and export TOP images without sending TouchDesigner objects to background threads.

![Typed request flows through a main-thread operator graph into a verified visual, project, and PNG artifact](docs/images/touchdesigner-scripting-showcase.webp)

_Illustrative workflow visualization generated with OpenAI ImageGen from the retained source in `docs/images/sources`. It is not a TouchDesigner screenshot or host-validation artifact. The header uses an approved operator-network reference motif rather than an official host mark._

## Install

TouchDesigner 2025 uses Python 3.11. Install this package into a matching external environment and expose that environment to TouchDesigner. The preferred TouchDesigner 2025 route is the built-in `TDPyEnvManager`; the Preferences dialog's external Python module path is also supported.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install dcc-mcp-touchdesigner
```

See [install.md](install.md) for the complete Windows and macOS setup, dependency isolation guidance, and startup configuration. TouchDesigner documents both [external Python packages](https://docs.derivative.ca/Python#Installing_Custom_Python_Packages) and the [TDPyEnvManager](https://docs.derivative.ca/Palette%3AtdPyEnvManager).

## Start in TouchDesigner

Run this from the Textport or an Execute DAT `onStart()` callback:

```python
import dcc_mcp_touchdesigner

server = dcc_mcp_touchdesigner.start_server()
print(server.mcp_url)
```

`start_server()` is idempotent inside one TouchDesigner process. It loads the bundled skill by default, selects an OS-assigned loopback port, starts the main-thread pump, and advertises the instance to a running DCC-MCP gateway. Stop it explicitly during project teardown when needed:

```python
dcc_mcp_touchdesigner.stop_server()
```

## Typed tools

| Tool | Contract | Risk |
| --- | --- | --- |
| `get_project_info` | Read redacted host/project identity, cook rate, real-time mode, and root count | Read-only |
| `list_operators` | List bounded direct/recursive operators with an optional family/type filter | Read-only |
| `inspect_operator` / `inspect_connections` | Read flags, cook diagnostics, and connector topology | Read-only |
| `get_op_parameters` | Read selected or bounded parameters from one operator | Read-only |
| `create_operator` | Create a documented operator type under an explicit COMP | Mutation |
| `connect_operators` | Connect an explicit output connector to an explicit input | Mutation |
| `disconnect_operator_input` | Disconnect one exact input without touching sibling connections | Idempotent mutation |
| `set_op_parameter` | Set one parameter and return its evaluated value | Idempotent mutation |
| `pulse_op_parameter` | Pulse one exact parameter with bounded frame/second duration | Mutation |
| `set_operator_flags` | Atomically update allowlisted flags with rollback | Idempotent mutation |
| `set_operator_layout` | Atomically set bounded Network Editor position/size fields with rollback | Idempotent mutation |
| `get_dat_content` / `set_dat_content` | Read/write bounded, language-independent Unicode Text/Table DAT content with SHA-256 concurrency | Read / mutation |
| `get_timeline_state` / `set_timeline_state` | Read or atomically update root frame/play/cook controls | Read / mutation |
| `capture_top` | Save one TOP to an explicit PNG path with size and SHA-256 metadata | File write |
| `save_project` | Save the current project to an explicit `.toe` path | File write |
| `delete_operator` | Delete one explicitly addressed non-root operator | Destructive |

All 19 tools have JSON input/output contracts and are dispatched on TouchDesigner's main thread. File-writing tools require an explicit absolute path and reject accidental overwrite unless `overwrite=true` is supplied. Root deletion and executable-DAT mutation are always rejected. The catalog exposes no arbitrary Python or expression-evaluation tool.

## Security controls

The public contract is typed-only: it has no arbitrary Python escape hatch. Recursive graph, parameter, connector, JSON, and DAT operations are bounded; DAT writes use optional SHA-256 optimistic concurrency and only target Text/Table DATs. DAT text is treated as arbitrary Unicode data rather than a finite language list: RTL text, combining marks, ZWJ sequences, and non-BMP characters are preserved without language detection or normalization. Operator and parameter identifiers still follow TouchDesigner's own naming rules. The adapter binds to loopback by default. Do not expose the per-instance port directly to an untrusted network. Use the DCC-MCP gateway when multiple instances or attributable agent sessions are required.

## Runtime configuration

| Variable | Purpose |
| --- | --- |
| `DCC_MCP_TOUCHDESIGNER_SKILL_PATHS` | Additional skill directories |
| `DCC_MCP_TOUCHDESIGNER_METRICS` | Enable Prometheus `/metrics` |
| `DCC_MCP_TOUCHDESIGNER_ENABLE_GATEWAY_FAILOVER` | Enable gateway failover; on by default |

## Development

```powershell
py -3.11 -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
dcc-mcp-cli lint src/dcc_mcp_touchdesigner/skills/touchdesigner-scripting --warnings-as-errors
python -m build
python -m twine check dist/*
```

Unit and contract tests use a deterministic TouchDesigner API double. A release additionally requires a real TouchDesigner process, six readiness checks, discovery of all 19 typed tools, and a create/connect/layout/set/pulse/DAT/timeline/capture/save/delete chain through `dcc-mcp-cli`; simulation alone is not release evidence.

## License

MIT
