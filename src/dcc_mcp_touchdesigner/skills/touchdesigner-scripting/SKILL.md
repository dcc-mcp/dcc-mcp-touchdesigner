---
name: touchdesigner-scripting
description: "Inspect and author TouchDesigner operator graphs through typed, main-thread-safe tools"
metadata:
  dcc-mcp:
    dcc: touchdesigner
    layer: authoring
    version: "0.1.0" # x-release-please-version
    tags: [touchdesigner, scripting, project, operator, node-graph]
    search-hint: "TouchDesigner inspect create connect operator TOP parameter save project capture"
    tools: tools.yaml
---

# TouchDesigner Scripting

Use these tools to inspect, author, connect, validate, save, and capture a live
TouchDesigner project. Every tool declares `affinity: main`; never access
TouchDesigner operators from a background thread.

## Recommended workflow

1. Call `get_project_info` and `list_operators` before editing.
2. Use `create_operator` with documented type names such as `noiseTOP` and
   `levelTOP`.
3. Wire compatible families with `connect_operators`, then use
   `set_op_parameter` and read the value back with `get_op_parameters`.
4. Export a representative TOP with `capture_top` and save the project with
   `save_project`; both return artifact hashes.
5. Use `delete_operator` only for explicitly named non-root nodes.

## Safety

- `save_project` and `capture_top` reject existing files unless `overwrite` is
  explicitly true.
- `/` cannot be deleted.
- `execute_python` is an escape hatch and can be disabled with
  `DCC_MCP_TOUCHDESIGNER_DISABLE_EXECUTE_PYTHON=1` or
  `DCC_MCP_DISABLE_ARBITRARY_SCRIPT=1`.
- Prefer the typed graph tools over arbitrary Python.
