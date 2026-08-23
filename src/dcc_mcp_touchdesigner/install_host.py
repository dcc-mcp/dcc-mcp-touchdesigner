"""TouchDesigner host and target-interpreter preflight boundaries."""

from __future__ import annotations

import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .__version__ import __version__
from ._core_compat import MIN_CORE_VERSION, _release_tuple
from .install_contract import EXIT_PREFLIGHT, InstallFailure

_HOST_VERSION = re.compile(r"TouchDesigner[. _-]*(20\d{2}\.\d+)", re.IGNORECASE)


def resolve_touchdesigner(value: Optional[Path]) -> Path:
    configured = value
    if configured is None and os.environ.get("DCC_MCP_TOUCHDESIGNER_PATH"):
        configured = Path(os.environ["DCC_MCP_TOUCHDESIGNER_PATH"])
    if configured is None:
        discovered = shutil.which("TouchDesigner.exe") or shutil.which("TouchDesigner")
        configured = Path(discovered) if discovered else None
    if configured is None:
        raise InstallFailure(EXIT_PREFLIGHT, "host", "TouchDesigner installation was not found")
    resolved = configured.expanduser().resolve()
    if resolved.is_dir():
        candidates = (
            resolved / "bin" / "TouchDesigner.exe",
            resolved / "Contents" / "MacOS" / "TouchDesigner",
        )
        resolved = next((candidate for candidate in candidates if candidate.is_file()), resolved)
    if not resolved.is_file():
        raise InstallFailure(EXIT_PREFLIGHT, "host", f"TouchDesigner executable not found: {resolved}")
    return resolved


def touchdesigner_version(executable: Path) -> str:
    configured = os.environ.get("DCC_MCP_TOUCHDESIGNER_VERSION", "").strip()
    candidate = configured or str(executable)
    if not configured:
        application = next((parent for parent in executable.parents if parent.suffix.lower() == ".app"), None)
        plist_path = application / "Contents" / "Info.plist" if application is not None else None
        if plist_path is not None and plist_path.is_file():
            try:
                with plist_path.open("rb") as stream:
                    metadata = plistlib.load(stream)
                candidate = str(
                    metadata.get("CFBundleShortVersionString") or metadata.get("CFBundleVersion") or candidate
                )
            except (OSError, plistlib.InvalidFileException):
                pass
    match = _HOST_VERSION.search(candidate)
    if match is None:
        match = re.search(r"^(20\d{2}\.\d+)$", candidate)
    if match is None:
        raise InstallFailure(
            EXIT_PREFLIGHT,
            "host_version",
            "TouchDesigner version was not present in the install path; set DCC_MCP_TOUCHDESIGNER_VERSION",
        )
    version_value = match.group(1)
    if int(version_value.split(".", 1)[0]) < 2025:
        raise InstallFailure(EXIT_PREFLIGHT, "host_version", "TouchDesigner 2025 or newer is required")
    return version_value


def resolve_python(value: Optional[Path], executable: Path) -> Path:
    configured = value
    if configured is None and os.environ.get("DCC_MCP_INSTALL_PYTHON"):
        configured = Path(os.environ["DCC_MCP_INSTALL_PYTHON"])
    if configured is None:
        candidates = (
            executable.with_name("python.exe"),
            executable.parent.parent / "Frameworks" / "Python.framework" / "bin" / "python3.11",
            Path(sys.executable),
        )
        configured = next((candidate for candidate in candidates if candidate.is_file()), None)
    if configured is None:
        raise InstallFailure(EXIT_PREFLIGHT, "python", "TouchDesigner-compatible Python was not found")
    resolved = configured.expanduser().resolve()
    if not resolved.is_file():
        raise InstallFailure(EXIT_PREFLIGHT, "python", f"Python interpreter not found: {resolved}")
    return resolved


def target_info(python: Path) -> dict[str, str]:
    code = (
        "import importlib.metadata as m, json, platform, site; "
        "print(json.dumps({'python_version': platform.python_version(), "
        "'dcc-mcp-core': m.version('dcc-mcp-core'), "
        "'dcc-mcp-touchdesigner': m.version('dcc-mcp-touchdesigner'), "
        "'site_packages': site.getsitepackages()[0]}))"
    )
    try:
        completed = subprocess.run([str(python), "-c", code], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallFailure(EXIT_PREFLIGHT, "python", str(exc)) from exc
    if completed.returncode:
        details = completed.stderr.strip().splitlines()
        raise InstallFailure(
            EXIT_PREFLIGHT,
            "python",
            details[-1] if details else "Target Python metadata query failed",
        )
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise InstallFailure(EXIT_PREFLIGHT, "python", "Invalid target Python metadata") from exc
    if not isinstance(payload, dict):
        raise InstallFailure(EXIT_PREFLIGHT, "python", "Target Python metadata must be an object")
    python_version = str(payload.get("python_version", ""))
    try:
        python_minor = tuple(int(item) for item in python_version.split(".")[:2])
    except ValueError:
        python_minor = ()
    if python_minor != (3, 11):
        raise InstallFailure(EXIT_PREFLIGHT, "python", "TouchDesigner 2025 requires Python 3.11")
    core_version = str(payload.get("dcc-mcp-core", ""))
    try:
        core_compatible = _release_tuple(core_version) >= _release_tuple(MIN_CORE_VERSION)
    except RuntimeError as exc:
        raise InstallFailure(EXIT_PREFLIGHT, "core", f"dcc-mcp-core has an invalid version: {core_version!r}") from exc
    if not core_compatible:
        raise InstallFailure(
            EXIT_PREFLIGHT,
            "core",
            f"dcc-mcp-core {core_version} is unsupported; {MIN_CORE_VERSION} or newer is required",
        )
    adapter_version = str(payload.get("dcc-mcp-touchdesigner", ""))
    if adapter_version != __version__:
        raise InstallFailure(
            EXIT_PREFLIGHT,
            "adapter",
            f"Target Python has dcc-mcp-touchdesigner {adapter_version}; installer is {__version__}",
        )
    site_packages_value = str(payload.get("site_packages", "")).strip()
    if not site_packages_value:
        raise InstallFailure(EXIT_PREFLIGHT, "python", "Target site-packages was not reported")
    site_packages = Path(site_packages_value).expanduser().resolve(strict=False)
    payload["site_packages"] = str(site_packages)
    return {str(key): str(item) for key, item in payload.items()}


def python_import_check(python: Path) -> dict[str, object]:
    if not python.is_file():
        return {"success": False, "reason": f"Python interpreter not found: {python}"}
    code = (
        "import dcc_mcp_touchdesigner, json; "
        "print(json.dumps({'success': True, 'version': dcc_mcp_touchdesigner.__version__}))"
    )
    try:
        completed = subprocess.run([str(python), "-c", code], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"success": False, "reason": str(exc)}
    if completed.returncode:
        details = completed.stderr.strip().splitlines()
        return {
            "success": False,
            "reason": details[-1] if details else "Target import failed",
        }
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return {"success": False, "reason": "Invalid target import response"}
    if not isinstance(payload, dict) or not payload.get("success"):
        return {"success": False, "reason": "Target import did not report success"}
    return payload
