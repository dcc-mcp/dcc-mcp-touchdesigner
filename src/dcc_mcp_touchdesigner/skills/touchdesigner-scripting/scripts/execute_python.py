"""Execute a Python expression or statement in TouchDesigner's Python environment.

Args:
    code: Python code to execute.

Returns:
    dict with output, result, and error keys.
"""

from __future__ import annotations

import io
import sys
from typing import Any

from dcc_mcp_touchdesigner.api import skill_entry, skill_error, skill_success


@skill_entry
def execute_python(code: str) -> dict[str, Any]:
    if not code or not code.strip():
        return skill_error("code must be a non-empty string")

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_out = io.StringIO()
    captured_err = io.StringIO()

    try:
        sys.stdout = captured_out
        sys.stderr = captured_err
        import td

        # Execute in the td module's namespace so op() etc. are available
        ns: dict[str, Any] = {"td": td}
        try:
            result = eval(code.strip(), ns)
        except SyntaxError:
            exec(code.strip(), ns)
            result = None
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        return skill_success(
            {
                "result": repr(result) if result is not None else None,
                "stdout": captured_out.getvalue(),
                "stderr": captured_err.getvalue(),
            }
        )
    except Exception as exc:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        return skill_error(
            f"{type(exc).__name__}: {exc}",
            data={
                "stdout": captured_out.getvalue(),
                "stderr": captured_err.getvalue(),
            },
        )
