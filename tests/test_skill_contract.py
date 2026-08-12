"""Packaged Skill metadata and result-envelope contract tests."""

from __future__ import annotations

import runpy
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).parent.parent / "src" / "dcc_mcp_touchdesigner" / "skills" / "touchdesigner-scripting"


def test_execute_python_policy_returns_core_error_envelope(monkeypatch):
    monkeypatch.setenv("DCC_MCP_TOUCHDESIGNER_DISABLE_EXECUTE_PYTHON", "1")
    namespace = runpy.run_path(str(SKILL_ROOT / "scripts" / "execute_python.py"))

    result = namespace["main"].__wrapped__("1 + 1")

    assert result["success"] is False
    assert result["error"] == "execute_python_disabled"
    assert result["message"] == "Python execution is disabled by adapter policy."


def test_tools_yaml_exposes_typed_authoring_and_artifact_chain():
    tools = yaml.safe_load((SKILL_ROOT / "tools.yaml").read_text(encoding="utf-8"))["tools"]
    by_name = {tool["name"]: tool for tool in tools}

    assert set(by_name) == {
        "capture_top",
        "connect_operators",
        "create_operator",
        "delete_operator",
        "execute_python",
        "get_op_parameters",
        "get_project_info",
        "list_operators",
        "save_project",
        "set_op_parameter",
    }
    assert all(tool["affinity"] == "main" for tool in tools)
    assert all(tool["source_file"].startswith("scripts/") for tool in tools)
    assert all(tool["output_schema"]["required"] == ["success", "message", "context"] for tool in tools)
    assert by_name["capture_top"]["input_schema"]["required"] == ["path", "output_path"]
    assert by_name["save_project"]["input_schema"]["required"] == ["path"]
