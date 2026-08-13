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

Use these 19 bounded tools to inspect, author, connect, validate, save, and
capture a live TouchDesigner project. Every tool declares `affinity: main`;
never access TouchDesigner operators from a background thread.

## Recommended workflow

1. Call `get_project_info` and `list_operators` before editing.
2. Use `inspect_operator`, `inspect_connections`, and `get_op_parameters` to
   capture the exact pre-mutation state.
3. Use `create_operator` with documented type names such as `noiseTOP` and
   `levelTOP`; wire them with `connect_operators`.
4. Use `set_op_parameter`, `pulse_op_parameter`, `set_operator_flags`,
   `set_operator_layout`, or `disconnect_operator_input` for one explicitly
   addressed mutation.
5. Read/write arbitrary Unicode Text/Table DAT content without a language
   allowlist, using SHA-256 optimistic concurrency, and control root time
   through the typed timeline tools.
6. Export a representative TOP with `capture_top` and save the project with
   `save_project`; both return artifact hashes.
7. Use `delete_operator` only for explicitly named non-root nodes.

## Safety

- `save_project` and `capture_top` reject existing files unless `overwrite` is
  explicitly true.
- `/` cannot be deleted.
- Recursive graph, parameter, connector, JSON, and DAT results have explicit
  size/count limits.
- DAT mutation is restricted to Text DAT and Table DAT; executable DAT types
  are rejected.
- DAT text is opaque Unicode data: never detect a language, normalize content,
  or assume LTR layout. TouchDesigner still owns identifier naming rules.
- The public tool catalog exposes no arbitrary Python, expression evaluator,
  or script execution escape hatch.
