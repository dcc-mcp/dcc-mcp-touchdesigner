# Installing dcc-mcp-touchdesigner

## Requirements

- TouchDesigner 2025 official build
- A Python environment matching TouchDesigner's embedded Python version
- `dcc-mcp-touchdesigner` and its `dcc-mcp-core` dependency installed into that environment

TouchDesigner 2025 currently embeds Python 3.11. Confirm the exact interpreter from the Textport before creating an environment:

```python
app.pythonExecutable
import sys

sys.version
```

Do not mix an environment built for a different Python minor version. Avoid overriding TouchDesigner's bundled NumPy or OpenCV unless the project explicitly owns and tests those versions.

## Preferred: TDPyEnvManager

TouchDesigner 2025 includes `TDPyEnvManager` in the Palette. It creates a project-local Python environment, adds it to TouchDesigner's import path, and can restore requirements at startup.

1. Add `TDPyEnvManager` from the Palette to the project.
2. Select Python vEnv mode and create a `.venv` beside the `.toe` project.
3. Open that environment's CLI from the component.
4. Install the adapter:

   ```text
   python -m pip install --upgrade pip
   python -m pip install dcc-mcp-touchdesigner
   ```

5. Restart TouchDesigner so its Python search path is rebuilt.

For a reproducible project, add this line to the project's `requirements.txt` and let the component restore it:

```text
dcc-mcp-touchdesigner==0.1.0
```

See Derivative's [TDPyEnvManager documentation](https://docs.derivative.ca/Palette%3AtdPyEnvManager) for `pyproject.toml`, `autoSetup`, and environment lifecycle options.

## Alternative: external Python 3.11 environment

Create a normal Python 3.11 virtual environment outside TouchDesigner:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install dcc-mcp-touchdesigner
```

In TouchDesigner, open **Edit > Preferences > Python**:

1. Enable **Add Externally Installed Python Site-Packages to Search Path**.
2. Set **Python 64-bit Module Path** to the environment's `Lib\site-packages` directory on Windows, or `lib/python3.11/site-packages` on macOS.
3. Restart TouchDesigner.

Derivative documents this path in [Installing Custom Python Packages](https://docs.derivative.ca/Python#Installing_Custom_Python_Packages).

## Verify imports

Open the Textport and run:

```python
import dcc_mcp_core
import dcc_mcp_touchdesigner

print(dcc_mcp_touchdesigner.__version__)
```

The `td` module is only available inside TouchDesigner. A normal terminal can validate package installation, but it cannot validate host dispatch or typed tool execution.

## Start and stop with the project

For manual testing:

```python
import dcc_mcp_touchdesigner

server = dcc_mcp_touchdesigner.start_server()
print(server.mcp_url)
```

For persistent startup, place the same call in an Execute DAT `onStart()` callback. Pair it with `stop_server()` in `onExit()`:

```python
def onStart():
    import dcc_mcp_touchdesigner

    dcc_mcp_touchdesigner.start_server()
    return


def onExit():
    import dcc_mcp_touchdesigner

    dcc_mcp_touchdesigner.stop_server()
    return
```

The server uses an OS-assigned loopback port and registers itself when a DCC-MCP gateway is available. Do not hard-code a port unless an isolated integration requires it.

## Verify readiness and tools

From a terminal with `dcc-mcp-cli` installed:

```powershell
dcc-mcp-cli list --output json
dcc-mcp-cli search --dcc-type touchdesigner --output json
```

For release acceptance, verify all six readiness checks and call a cheap read-only typed tool before any mutation. Route later calls to the exact `instance_id` when more than one TouchDesigner process is running.

## Troubleshooting

- `No module named dcc_mcp_touchdesigner`: confirm the configured site-packages path and restart TouchDesigner.
- Binary import or DLL load errors: rebuild the environment with the exact Python minor version reported by `sys.version`.
- `No module named td` in a terminal: expected; run host API code inside TouchDesigner.
- Instance absent from the CLI: compare the registry directory and gateway environment used by TouchDesigner and the terminal.
- HTTP server is available but host tools time out: confirm the project is cooking and the adapter's `td.run()` main-thread pump has not been stopped.
- A legacy client asks for `execute_python`: upgrade it to the typed graph,
  DAT, parameter, and timeline tools; arbitrary Python is intentionally not a
  public adapter capability.
