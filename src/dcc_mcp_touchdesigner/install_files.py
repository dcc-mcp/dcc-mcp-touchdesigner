"""Receipt-owned staged file operations for TouchDesigner integration."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any

from .__version__ import __version__
from .install_contract import EXIT_INSTALL, EXIT_REQUIRES_RESTART, SCHEMA_VERSION, InstallFailure


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_write(path: Path, payload: bytes, mode: int = 0o600) -> bool:
    if path.is_file() and path.read_bytes() == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def load_receipt(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallFailure(EXIT_INSTALL, "receipt", f"Invalid install receipt: {exc}") from exc
    if not isinstance(payload, dict):
        raise InstallFailure(EXIT_INSTALL, "receipt", "Install receipt must be a JSON object")
    return payload


def receipt_owns(receipt: dict[str, Any] | None, root: Path) -> bool:
    if not (
        receipt
        and receipt.get("schema_version") == SCHEMA_VERSION
        and receipt.get("dcc_type") == "touchdesigner"
        and receipt.get("owner") == "dcc-mcp-touchdesigner"
        and receipt.get("integration_root") == str(root)
    ):
        return False
    files = receipt.get("files")
    if not isinstance(files, list):
        return False
    owned_paths = {
        str(item.get("path")) for item in files if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    expected_paths = {str(root / "bootstrap.py"), str(root / "execute_dat.py")}
    return owned_paths == expected_paths


def inspect_install(root: Path, receipt_file: Path) -> dict[str, Any]:
    receipt = load_receipt(receipt_file)
    expected_paths = [root / "bootstrap.py", root / "execute_dat.py"]
    existing = [path.is_file() for path in expected_paths]
    valid = receipt_owns(receipt, root)
    hashes_match = False
    if valid and all(existing):
        expected = {
            str(item.get("path")): item.get("sha256") for item in receipt.get("files", []) if isinstance(item, dict)
        }
        hashes_match = all(expected.get(str(path)) == sha256(path.read_bytes()) for path in expected_paths)
    version_current = bool(valid and receipt.get("adapter_version") == __version__)
    if receipt is None and not any(existing):
        state = "fresh"
    elif not valid or not all(existing):
        state = "partial"
    elif not hashes_match:
        state = "repair"
    elif not version_current:
        state = "upgrade"
    else:
        state = "current"
    return {
        "installation_state": state,
        "receipt": receipt,
        "checks": {
            "receipt_exists": receipt_file.is_file(),
            "receipt_valid": valid,
            "bootstrap_exists": existing[0],
            "execute_dat_exists": existing[1],
            "artifact_hashes_match": hashes_match,
            "version_stamp_current": version_current,
        },
    }


def install_artifacts(report: dict[str, Any], artifacts: dict[str, str]) -> dict[str, object]:
    root = Path(report["integration_root"])
    receipt_file = Path(report["receipt_path"])
    previous_receipt = load_receipt(receipt_file)
    targets = {root / name: content.encode("utf-8") for name, content in artifacts.items()}
    if any(path.exists() for path in targets) and not receipt_owns(previous_receipt, root):
        raise InstallFailure(EXIT_INSTALL, "ownership", f"Refusing to replace unowned files in {root}")
    previous = {path: (path.read_bytes(), path.stat().st_mode) if path.is_file() else None for path in targets}
    receipt_payload = {
        "schema_version": SCHEMA_VERSION,
        "dcc_type": "touchdesigner",
        "owner": "dcc-mcp-touchdesigner",
        "adapter_version": report["adapter_version"],
        "core_version": report["core_version"],
        "touchdesigner_version": report["touchdesigner_version"],
        "dcc_path": report["dcc_path"],
        "python": report["python"],
        "site_packages": report["site_packages"],
        "integration_root": str(root),
        "files": [{"path": str(path), "sha256": sha256(payload)} for path, payload in targets.items()],
    }
    receipt_bytes = (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode()
    changed: list[Path] = []
    try:
        for path, payload in targets.items():
            if atomic_write(path, payload):
                changed.append(path)
        receipt_changed = atomic_write(receipt_file, receipt_bytes)
    except OSError as exc:
        try:
            for path in reversed(changed):
                prior = previous[path]
                if prior is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, prior[0], prior[1])
        except OSError as rollback_exc:
            raise InstallFailure(
                EXIT_INSTALL,
                "rollback",
                f"Install failed ({exc}); rollback failed ({rollback_exc})",
            ) from rollback_exc
        if isinstance(exc, PermissionError):
            raise InstallFailure(EXIT_REQUIRES_RESTART, "artifact_locked", str(exc)) from exc
        raise InstallFailure(EXIT_INSTALL, "install", str(exc)) from exc
    return {
        "id": "stage-bootstrap",
        "status": "installed",
        "source": "release-bootstrap",
        "bootstrap_file": str(root / "bootstrap.py"),
        "execute_dat_file": str(root / "execute_dat.py"),
        "changed": bool(changed) or receipt_changed,
    }


def uninstall_artifacts(root: Path, receipt_file: Path) -> dict[str, object]:
    receipt = load_receipt(receipt_file)
    targets = [root / "bootstrap.py", root / "execute_dat.py"]
    if receipt is None and not any(path.exists() for path in targets):
        return {"id": "remove-bootstrap", "status": "uninstalled", "changed": False}
    if not receipt_owns(receipt, root):
        raise InstallFailure(
            EXIT_INSTALL,
            "ownership",
            "Install receipt does not prove ownership of the TouchDesigner integration",
        )
    staged: list[tuple[Path, Path]] = []
    try:
        for path in (*targets, receipt_file):
            if not path.exists():
                continue
            backup = path.with_name(f".{path.name}.{secrets.token_hex(8)}.uninstall")
            os.replace(path, backup)
            staged.append((path, backup))
    except OSError as exc:
        for original, backup in reversed(staged):
            if backup.exists():
                os.replace(backup, original)
        if isinstance(exc, PermissionError):
            raise InstallFailure(EXIT_REQUIRES_RESTART, "artifact_locked", str(exc)) from exc
        raise InstallFailure(EXIT_INSTALL, "uninstall", str(exc)) from exc
    for _original, backup in staged:
        backup.unlink(missing_ok=True)
    return {"id": "remove-bootstrap", "status": "uninstalled", "changed": bool(staged)}
