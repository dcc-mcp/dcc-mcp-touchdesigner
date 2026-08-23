# Installing dcc-mcp-touchdesigner

This is the canonical TouchDesigner adapter runbook. Agents should read the
[raw file](https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-touchdesigner/main/install.md)
before changing an installation.

## Requirements

- An official TouchDesigner 2025 build on Windows or macOS.
- TouchDesigner's Python 3.11 interpreter, or a Python 3.11 environment whose
  `site-packages` directory is exposed to TouchDesigner.
- `dcc-mcp-touchdesigner` and `dcc-mcp-core>=0.19.91` installed in that exact
  interpreter.

TouchDesigner reports the interpreter and version from the Textport:

```python
app.pythonExecutable
import sys
sys.version
```

Do not mix Python minor versions or replace TouchDesigner's bundled NumPy or
OpenCV unless the project owns and tests those binary dependencies.

## Supported versions

| Platform | Host support | Notes |
| --- | --- | --- |
| Windows | TouchDesigner 2025, Python 3.11 | Pass `--dcc-path` when the executable is not discoverable. |
| macOS | TouchDesigner 2025, Python 3.11 | The CLI accepts the executable inside `TouchDesigner.app`. |
| Linux | Planning and package development only | TouchDesigner is not available for Linux. |

The installer rejects older hosts, a non-3.11 target interpreter, an older
Core, or an adapter version that is not importable by the target interpreter.

## Agent quick path

Install the package into the target Python 3.11 environment, then inspect the
machine-readable plan before applying it:

```text
python -m pip install --upgrade dcc-mcp-touchdesigner
dcc-mcp-touchdesigner install --dry-run --json
dcc-mcp-touchdesigner install --yes --json
```

Use `--dcc-path PATH` and `--python PATH` if discovery cannot select the exact
host and interpreter. Every verb also accepts `--json`; mutation verbs require
`--yes`, and `--dry-run` never writes files.

The installer stages an idempotent bootstrap and receipt at
`~/.dcc-mcp/receipts/touchdesigner.json`. A successful first install returns
exit code `50` (`requires_restart`) and exactly one machine-executable
`next_steps` entry. Apply that `file_edit` to create the named Execute DAT in
the current project with Start and Exit callbacks enabled, save the project,
and restart TouchDesigner. The CLI does not pretend that a project-owned DAT
or host restart can be completed from an external process.

After restart, inspect and verify the installation:

```text
dcc-mcp-touchdesigner status --json
dcc-mcp-touchdesigner verify --json
```

`verify` succeeds only when the staged artifacts match the receipt, the target
interpreter imports both packages, no latest bootstrap error is recorded, the
Core readiness checks pass, and the read-only
`touchdesigner_scripting__get_project_info` probe succeeds.

## Manual path

TouchDesigner 2025 includes `TDPyEnvManager` in the Palette. It can create a
project-local `.venv`, add it to the host import path, and restore requirements
at startup:

1. Add `TDPyEnvManager` from the Palette and select Python vEnv mode.
2. Create a `.venv` beside the `.toe` file and open that environment's CLI.
3. Install `dcc-mcp-touchdesigner` and run the agent quick path with that
   environment's Python.

For an external environment, create Python 3.11 and install the package:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip dcc-mcp-touchdesigner
```

On macOS, use the equivalent `python3.11 -m venv .venv` and
`.venv/bin/python`. In **Edit > Preferences > Python**, enable external Python
site-packages and select the environment's `site-packages` directory. Restart
TouchDesigner after changing the import path.

If the lifecycle CLI is unavailable, create an Execute DAT whose `onStart`
calls `dcc_mcp_touchdesigner.start_server()` and whose `onExit` calls
`dcc_mcp_touchdesigner.stop_server()`. The generated `file_edit` is preferred
because it reuses the release bootstrap and captures startup errors.

## Verify

Run:

```text
dcc-mcp-touchdesigner status --json
dcc-mcp-touchdesigner verify --json
```

Exit code `0` means directly usable. Exit code `40` means verification failed;
inspect `verify.failure_stage`, `verify.failure_reason`, and `next_steps` in the
JSON response. A normal terminal can prove package imports, but it cannot prove
TouchDesigner dispatch, the main-thread scheduler, or typed tool execution.

## Upgrade

Upgrade the target environment, review the plan, and apply the staged replace:

```text
python -m pip install --upgrade dcc-mcp-touchdesigner
dcc-mcp-touchdesigner upgrade --dry-run --json
dcc-mcp-touchdesigner upgrade --yes --json
```

The upgrade preserves owned artifacts until replacements are staged, records
their SHA-256 digests, and restores the prior state if installation fails.
Reapply the returned Execute DAT `file_edit` if its content changed, save, and
restart before running `verify`.

## Uninstall

Review status, then remove only artifacts owned by the receipt:

```text
dcc-mcp-touchdesigner status --json
dcc-mcp-touchdesigner uninstall --dry-run --json
dcc-mcp-touchdesigner uninstall --yes --json
```

Delete the project Execute DAT named by the previous install response and save
the project. The package itself remains in the Python environment so package
management stays with pip or `TDPyEnvManager`.

## Troubleshooting

- `preflight` failure: pass explicit `--dcc-path` and `--python` values, then
  confirm the target is TouchDesigner 2025 with Python 3.11 and Core 0.19.91 or
  newer.
- `installation_state` is `partial` or `repair`: rerun
  `dcc-mcp-touchdesigner install --yes --json`. The installer only replaces
  receipt-owned files and fails closed on unrelated content.
- `installation_state` is `upgrade`: update the target package, then run the
  upgrade command above.
- `bootstrap` failure: inspect the bounded error record named in the verify
  response, fix the target environment, and restart TouchDesigner.
- `No module named dcc_mcp_touchdesigner`: confirm the Preferences or
  `TDPyEnvManager` site-packages path and restart.
- Binary import or DLL load errors: rebuild the environment with the exact
  Python minor version reported by TouchDesigner.
- `No module named td` in a terminal: expected; the `td` module exists only in
  TouchDesigner.
- Instance absent from discovery: compare the registry and gateway environment
  used by TouchDesigner and the terminal, then rerun `verify`.
- Legacy clients requesting `execute_python` must use the registered typed
  graph, DAT, parameter, and timeline tools; arbitrary Python is not exposed.

TouchDesigner references:
[TDPyEnvManager](https://docs.derivative.ca/Palette%3AtdPyEnvManager) and
[Installing Custom Python Packages](https://docs.derivative.ca/Python#Installing_Custom_Python_Packages).
