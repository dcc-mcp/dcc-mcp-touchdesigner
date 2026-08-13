"""Packaged Skill metadata and result-envelope contract tests."""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import yaml
from dcc_mcp_core import validate_skill

SKILL_ROOT = Path(__file__).parent.parent / "src" / "dcc_mcp_touchdesigner" / "skills" / "touchdesigner-scripting"


def test_tools_yaml_exposes_typed_authoring_and_artifact_chain():
    tools = yaml.safe_load((SKILL_ROOT / "tools.yaml").read_text(encoding="utf-8"))["tools"]
    by_name = {tool["name"]: tool for tool in tools}

    assert set(by_name) == {
        "capture_top",
        "connect_operators",
        "create_operator",
        "delete_operator",
        "disconnect_operator_input",
        "get_dat_content",
        "get_op_parameters",
        "get_project_info",
        "get_timeline_state",
        "inspect_connections",
        "inspect_operator",
        "list_operators",
        "pulse_op_parameter",
        "save_project",
        "set_dat_content",
        "set_op_parameter",
        "set_operator_flags",
        "set_operator_layout",
        "set_timeline_state",
    }
    assert all(tool["affinity"] == "main" for tool in tools)
    assert all(tool["source_file"].startswith("scripts/") for tool in tools)
    assert all(tool["input_schema"]["additionalProperties"] is False for tool in tools)
    assert all(tool["output_schema"]["required"] == ["success", "message", "context"] for tool in tools)
    assert by_name["capture_top"]["input_schema"]["required"] == ["path", "output_path"]
    assert by_name["save_project"]["input_schema"]["required"] == ["path"]
    assert "execute_python" not in by_name
    assert len(tools) == 19

    frontmatter = yaml.safe_load((SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
    assert frontmatter["metadata"]["dcc-mcp"]["version"] == version("dcc-mcp-touchdesigner")

    report = validate_skill(str(SKILL_ROOT))
    assert not report.issues, report.issues


def test_arbitrary_python_script_is_not_packaged():
    assert not (SKILL_ROOT / "scripts" / "execute_python.py").exists()


def test_capability_manifest_declares_typed_only_public_surface():
    from dcc_mcp_touchdesigner.capabilities import touchdesigner_capabilities_dict

    extensions = touchdesigner_capabilities_dict()["extensions"]
    assert extensions["typed_dat_content"] is True
    assert extensions["typed_timeline"] is True
    assert extensions["typed_operator_layout"] is True
    assert extensions["arbitrary_python_tool"] is False
    assert "python_expression" not in extensions
