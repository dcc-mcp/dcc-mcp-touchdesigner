from pathlib import Path


def test_install_runbook_publishes_agent_first_lifecycle():
    root = Path(__file__).parents[1]
    text = (root / "install.md").read_text(encoding="utf-8")

    for heading in (
        "## Requirements",
        "## Supported versions",
        "## Agent quick path",
        "## Manual path",
        "## Verify",
        "## Upgrade",
        "## Uninstall",
        "## Troubleshooting",
    ):
        assert heading in text
    for platform in ("Windows", "macOS", "Linux"):
        assert platform in text
    for command in (
        "dcc-mcp-touchdesigner install --dry-run --json",
        "dcc-mcp-touchdesigner install --yes --json",
        "dcc-mcp-touchdesigner status --json",
        "dcc-mcp-touchdesigner verify --json",
        "dcc-mcp-touchdesigner upgrade --yes --json",
        "dcc-mcp-touchdesigner uninstall --yes --json",
    ):
        assert command in text
    assert "https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-touchdesigner/main/install.md" in text
    assert ".dcc-mcp/receipts/touchdesigner.json" in text
    assert "TouchDesigner is not available for Linux" in text
    assert "dcc-mcp-touchdesigner==0.1.0" not in text


def test_readme_routes_agents_to_the_lifecycle_cli():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    assert "dcc-mcp-touchdesigner install --dry-run --json" in readme
    assert "dcc-mcp-touchdesigner install --yes --json" in readme
    assert "dcc-mcp-touchdesigner verify --json" in readme
    assert "install.md" in readme
