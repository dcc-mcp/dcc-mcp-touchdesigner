"""Thin compatibility facade for the shared Install SOP v1 contract."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    import dcc_mcp_core as _core

    # `INSTALL_SOP_SCHEMA_REVISION` is the revision of the published Install SOP
    # schema *artifact* (`adapter-install-sop-vN.schema.json`), 2 since
    # dcc-mcp-core 0.20.36. It is NOT the value of the `schema_version` field
    # that the artifact pins on a report document: that field is a separate,
    # stable counter declared as `properties.schema_version.const` and stays at
    # 1, because artifact revisions only add optional members.
    #
    # Core 0.20.40 renamed this from `INSTALL_SOP_SCHEMA_VERSION`: the old name
    # read like the report field above while it actually carried the artifact
    # revision. It survives one release as a deprecated alias, and the rename
    # here is what the shared adapter contract (A001) asks consumers to do where
    # the value genuinely means the artifact revision.
    ARTIFACT_SCHEMA_VERSION = _core.INSTALL_SOP_SCHEMA_REVISION
    EXIT_OK = _core.INSTALL_EXIT_OK
    EXIT_PREFLIGHT = _core.INSTALL_EXIT_PREFLIGHT
    EXIT_ACQUIRE = _core.INSTALL_EXIT_ACQUIRE
    EXIT_INSTALL = _core.INSTALL_EXIT_INSTALL
    EXIT_VERIFY = _core.INSTALL_EXIT_VERIFY
    EXIT_REQUIRES_RESTART = _core.INSTALL_EXIT_REQUIRES_RESTART
except AttributeError:  # Compatibility until Core #2252 is in the minimum release.
    # `None`, not 1: a core predating the constant has no artifact revision to
    # report, and a placeholder 1 reads as if the artifact revision were known
    # to be 1 on old cores. Only tests consume this name.
    ARTIFACT_SCHEMA_VERSION = None
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

# The install receipt is this adapter's own on-disk format, not an Install SOP
# report: it carries `owner`, `integration_root` and `files`, none of which the
# published schema defines. It therefore needs its own version counter rather
# than the report field above -- reusing the report field here is the same
# conflation one layer down, and it is what locked affected installs out of the
# CLI: a receipt written as `2` stopped matching once the report field was
# corrected to 1, and `receipt_owns()` then refused both repair and removal.
RECEIPT_SCHEMA_VERSION = 1

# Receipt versions this adapter must still accept on read. `2` is what releases
# that resolved core >= 0.20.36 wrote, by the conflation fixed above; those
# receipts describe real installs and have to stay readable so the CLI can
# repair or remove them. The set is closed: `RECEIPT_SCHEMA_VERSION` no longer
# tracks core, so no further value can ever be written.
#
# A tuple, not a set: membership is tested against a value read from JSON, so it
# may be any type. `in` on a set hashes its operand and raises TypeError on an
# unhashable one (a hand-edited or badly restored receipt carrying `[]`), while
# `in` on a tuple compares by equality and simply returns False. `receipt_owns`
# feeds `inspect_install`, which every lifecycle verb calls, so raising here
# would turn a corrupt receipt into a traceback on the very commands a stuck
# user needs -- `cli.py` only handles InstallFailure.
RECEIPT_READABLE_SCHEMA_VERSIONS = (1, 2)

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
