"""Install SOP orchestration for TouchDesigner-owned integration artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional

from dcc_mcp_core.install_lifecycle import wait_for_sidecar_ready

from .__version__ import __version__
from .bootstrap import bootstrap_error_summary, render_bootstrap, render_execute_dat
from .install_contract import SCHEMA_VERSION, empty_verify, runtime_core_version
from .install_files import inspect_install, install_artifacts, uninstall_artifacts
from .install_host import (
    python_import_check,
    resolve_python,
    resolve_touchdesigner,
    target_info,
    touchdesigner_version,
)


def integration_root() -> Path:
    return Path.home() / ".dcc-mcp" / "touchdesigner"


def receipt_path() -> Path:
    return Path.home() / ".dcc-mcp" / "receipts" / "touchdesigner.json"


def plan(verb: str, dcc_path: Optional[Path], python_value: Optional[Path]) -> dict[str, Any]:
    executable = resolve_touchdesigner(dcc_path)
    host_version = touchdesigner_version(executable)
    python = resolve_python(python_value, executable)
    info = target_info(python)
    root = integration_root()
    bootstrap_path = root / "bootstrap.py"
    execute_dat_path = root / "execute_dat.py"
    bootstrap = render_bootstrap(repr(info["site_packages"]))
    execute_dat = render_execute_dat(bootstrap_path)
    inspection = inspect_install(root, receipt_path())
    next_step = {
        "id": "create-execute-dat",
        "description": "Create one Execute DAT with Start and Exit callbacks enabled",
        "file_edit": {
            "path": "touchdesigner://current-project/execute-dat/dcc_mcp_startup",
            "action": "create",
            "content": execute_dat,
        },
        "why": "TouchDesigner stores startup callbacks inside the project and requires a restart",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "planned",
        "dcc_type": "touchdesigner",
        "verb": verb,
        "adapter_version": __version__,
        "core_version": info["dcc-mcp-core"],
        "touchdesigner_version": host_version,
        "dcc_path": str(executable),
        "python": str(python),
        "python_version": info["python_version"],
        "site_packages": info["site_packages"],
        "integration_root": str(root),
        "installation_state": inspection["installation_state"],
        "steps": [
            {"id": "preflight", "status": "ok", "touchdesigner_version": host_version},
            {"id": "resolve-python", "status": "ok", "path": str(python)},
            {
                "id": "stage-bootstrap",
                "status": "planned",
                "source": "release-bootstrap",
                "bootstrap_file": str(bootstrap_path),
                "execute_dat_file": str(execute_dat_path),
                "bootstrap_sha256": hashlib.sha256(bootstrap.encode()).hexdigest(),
            },
            {"id": verb, "status": "planned"},
        ],
        "next_steps": [next_step],
        "receipt_path": str(receipt_path()),
        "verify": empty_verify(),
        "_artifacts": {"bootstrap.py": bootstrap, "execute_dat.py": execute_dat},
    }


def apply_install(report: dict[str, Any]) -> dict[str, Any]:
    artifacts = report.pop("_artifacts")
    stage = install_artifacts(report, artifacts)
    report["status"] = "requires_restart"
    report["installation_state"] = "current"
    report["steps"] = [stage if item["id"] == "stage-bootstrap" else item for item in report["steps"]]
    report["steps"][-1]["status"] = "installed"
    return report


def status_report() -> dict[str, Any]:
    root = integration_root()
    inspection = inspect_install(root, receipt_path())
    state = inspection["installation_state"]
    action = "verify" if state == "current" else "install"
    if state == "upgrade":
        action = "upgrade"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "dcc_type": "touchdesigner",
        "verb": "status",
        "adapter_version": __version__,
        "core_version": runtime_core_version(),
        "installation_state": state,
        "checks": inspection["checks"],
        "steps": [{"id": "inspect-install", "status": "ok"}],
        "next_steps": [
            {
                "id": action,
                "description": f"Run {action} for the TouchDesigner integration",
                "command": [
                    "dcc-mcp-touchdesigner",
                    action,
                    "--json",
                    *([] if action == "verify" else ["--yes"]),
                ],
                "why": f"The detected installation state is {state}",
            }
        ],
        "receipt_path": str(receipt_path()),
        "verify": empty_verify(),
    }


def uninstall_report(dry_run: bool) -> dict[str, Any]:
    root = integration_root()
    inspection = inspect_install(root, receipt_path())
    if dry_run:
        step = {
            "id": "remove-bootstrap",
            "status": "planned",
            "changed": inspection["installation_state"] != "fresh",
        }
        status = "planned"
        state = inspection["installation_state"]
    else:
        step = uninstall_artifacts(root, receipt_path())
        status = "ok"
        state = "fresh"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "dcc_type": "touchdesigner",
        "verb": "uninstall",
        "adapter_version": __version__,
        "core_version": runtime_core_version(),
        "installation_state": state,
        "steps": [step],
        "next_steps": [],
        "receipt_path": str(receipt_path()),
        "verify": empty_verify(),
    }


def verify_report(python_value: Optional[Path], timeout: float) -> dict[str, Any]:
    root = integration_root()
    inspection = inspect_install(root, receipt_path())
    bootstrap = bootstrap_error_summary()
    result: dict[str, Any] = {
        "directly_usable": False,
        "failure_stage": None,
        "failure_reason": None,
        "artifact": {"success": False},
        "import": {"success": False},
        "bootstrap": bootstrap,
        "readiness": {"success": False},
    }
    if inspection["installation_state"] != "current":
        result.update(
            failure_stage="artifact",
            failure_reason=f"Install artifacts are {inspection['installation_state']}",
        )
    else:
        result["artifact"] = {"success": True, **inspection["checks"]}
        receipt = inspection["receipt"]
        configured_python = python_value or Path(str(receipt.get("python", "")))
        result["import"] = python_import_check(configured_python.expanduser().resolve())
        if not result["import"].get("success"):
            result.update(
                failure_stage="import",
                failure_reason=result["import"].get("reason", "Target import failed"),
            )
        elif bootstrap["last"] is not None and not bootstrap["last"].get("success"):
            result.update(
                failure_stage="bootstrap",
                failure_reason=bootstrap["last"].get("reason", "TouchDesigner bootstrap failed"),
            )
        else:
            readiness = wait_for_sidecar_ready(
                dcc_type="touchdesigner",
                timeout_secs=max(0.0, timeout),
                probe_tool="touchdesigner_scripting__get_project_info",
            )
            result["readiness"] = readiness
            if not readiness.get("success"):
                result.update(
                    failure_stage="readiness",
                    failure_reason=readiness.get("message", "TouchDesigner adapter is not ready"),
                )
            else:
                result["directly_usable"] = True
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if result["directly_usable"] else "failed",
        "dcc_type": "touchdesigner",
        "verb": "verify",
        "adapter_version": __version__,
        "core_version": runtime_core_version(),
        "installation_state": inspection["installation_state"],
        "steps": [
            {
                "id": "verify-to-usable",
                "status": "ok" if result["directly_usable"] else "failed",
            }
        ],
        "next_steps": [] if result["directly_usable"] else status_report()["next_steps"],
        "receipt_path": str(receipt_path()),
        "verify": result,
    }
