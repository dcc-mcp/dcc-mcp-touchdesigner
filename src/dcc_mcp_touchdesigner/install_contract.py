"""Thin compatibility facade for the shared Install SOP v1 contract."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    import dcc_mcp_core as _core

    SCHEMA_VERSION = _core.INSTALL_SOP_SCHEMA_VERSION
    EXIT_OK = _core.INSTALL_EXIT_OK
    EXIT_PREFLIGHT = _core.INSTALL_EXIT_PREFLIGHT
    EXIT_ACQUIRE = _core.INSTALL_EXIT_ACQUIRE
    EXIT_INSTALL = _core.INSTALL_EXIT_INSTALL
    EXIT_VERIFY = _core.INSTALL_EXIT_VERIFY
    EXIT_REQUIRES_RESTART = _core.INSTALL_EXIT_REQUIRES_RESTART
except AttributeError:  # Compatibility until Core #2252 is in the minimum release.
    SCHEMA_VERSION = 1
    EXIT_OK, EXIT_PREFLIGHT, EXIT_ACQUIRE = 0, 10, 20
    EXIT_INSTALL, EXIT_VERIFY, EXIT_REQUIRES_RESTART = 30, 40, 50

LIFECYCLE_VERBS = {"install", "status", "verify", "uninstall", "upgrade"}


class InstallFailure(ValueError):
    def __init__(self, exit_code: int, stage: str, reason: str):
        super().__init__(reason)
        self.exit_code = exit_code
        self.stage = stage
        self.reason = reason


def empty_verify() -> dict[str, object]:
    return {"directly_usable": False, "failure_stage": None, "failure_reason": None}


def runtime_core_version() -> str:
    try:
        return version("dcc-mcp-core")
    except PackageNotFoundError:
        return "unavailable"
