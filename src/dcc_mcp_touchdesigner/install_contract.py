"""Thin compatibility facade for the shared Install SOP v1 contract."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    import dcc_mcp_core as _core

    # `INSTALL_SOP_SCHEMA_VERSION` is the revision of the published Install SOP
    # schema *artifact* (`adapter-install-sop-vN.schema.json`), 2 since
    # dcc-mcp-core 0.20.36. It is NOT the value of the `schema_version` field
    # that the artifact pins on a report document: that field is a separate,
    # stable counter declared as `properties.schema_version.const` and stays at
    # 1, because artifact revisions only add optional members.
    ARTIFACT_SCHEMA_VERSION = _core.INSTALL_SOP_SCHEMA_VERSION
    EXIT_OK = _core.INSTALL_EXIT_OK
    EXIT_PREFLIGHT = _core.INSTALL_EXIT_PREFLIGHT
    EXIT_ACQUIRE = _core.INSTALL_EXIT_ACQUIRE
    EXIT_INSTALL = _core.INSTALL_EXIT_INSTALL
    EXIT_VERIFY = _core.INSTALL_EXIT_VERIFY
    EXIT_REQUIRES_RESTART = _core.INSTALL_EXIT_REQUIRES_RESTART
except AttributeError:  # Compatibility until Core #2252 is in the minimum release.
    ARTIFACT_SCHEMA_VERSION = 1
    EXIT_OK, EXIT_PREFLIGHT, EXIT_ACQUIRE = 0, 10, 20
    EXIT_INSTALL, EXIT_VERIFY, EXIT_REQUIRES_RESTART = 30, 40, 50

# Value of the report document's own `schema_version` field, pinned by the
# published artifact at `properties.schema_version.const`. It is deliberately
# NOT derived from `ARTIFACT_SCHEMA_VERSION`: conflating the two made every
# doctor/verify/install report carry the artifact revision (2) and fail
# validation against the very schema it claims to follow, as soon as the
# resolved core reached 0.20.36.
#
# Kept in sync with `load_install_sop_schema()["properties"]["schema_version"]
# ["const"]` by tests/test_install_lifecycle.py, which fails when the resolved
# core drifts.
SCHEMA_VERSION = 1

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
