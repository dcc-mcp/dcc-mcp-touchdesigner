"""Agent-first installation lifecycle CLI for TouchDesigner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from .__version__ import __version__
from .install_contract import (
    EXIT_INSTALL,
    EXIT_REQUIRES_RESTART,
    EXIT_VERIFY,
    LIFECYCLE_VERBS,
    SCHEMA_VERSION,
    InstallFailure,
    empty_verify,
    runtime_core_version,
)
from .install_lifecycle import (
    apply_install,
    plan,
    receipt_path,
    status_report,
    uninstall_report,
    verify_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dcc-mcp-touchdesigner")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for verb in sorted(LIFECYCLE_VERBS):
        lifecycle = subparsers.add_parser(verb)
        lifecycle.add_argument("--dcc-path", type=Path)
        lifecycle.add_argument("--python", type=Path, dest="python_value")
        lifecycle.add_argument("--json", action="store_true", dest="as_json")
        lifecycle.add_argument("--yes", action="store_true")
        lifecycle.add_argument("--dry-run", action="store_true")
        lifecycle.add_argument("--timeout", type=float, default=10.0)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            report = status_report()
            if args.as_json:
                print(json.dumps(report, sort_keys=True))
            else:
                print(f"status: {report['installation_state']}")
            return 0
        if args.command == "verify":
            report = verify_report(args.python_value, args.timeout)
            if args.as_json:
                print(json.dumps(report, sort_keys=True))
            else:
                print(f"verify: {report['status']}")
            return 0 if report["verify"]["directly_usable"] else EXIT_VERIFY
        if args.command == "uninstall":
            if not args.dry_run and not args.yes:
                raise InstallFailure(EXIT_INSTALL, "confirmation", "Use --yes to uninstall")
            report = uninstall_report(args.dry_run)
            if args.as_json:
                print(json.dumps(report, sort_keys=True))
            else:
                print(f"uninstall: {report['status']}")
            return 0
        report = plan(args.command, args.dcc_path, args.python_value)
        if not args.dry_run and not args.yes:
            raise InstallFailure(EXIT_INSTALL, "confirmation", "Use --yes to apply lifecycle changes")
        if not args.dry_run and args.command in {"install", "upgrade"}:
            report = apply_install(report)
        elif not args.dry_run:
            raise InstallFailure(EXIT_INSTALL, "apply", f"{args.command} is not implemented yet")
    except InstallFailure as exc:
        next_steps = []
        if exc.exit_code == EXIT_REQUIRES_RESTART:
            command = ["dcc-mcp-touchdesigner", args.command, "--yes", "--json"]
            if args.dcc_path is not None:
                command.extend(["--dcc-path", str(args.dcc_path)])
            if args.python_value is not None:
                command.extend(["--python", str(args.python_value)])
            next_steps = [
                {
                    "id": "restart-and-retry",
                    "description": "Close TouchDesigner, retry the lifecycle command, then relaunch it",
                    "command": command,
                    "why": "TouchDesigner or its integration artifact is still locked",
                }
            ]
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "requires_restart" if exc.exit_code == EXIT_REQUIRES_RESTART else "failed",
            "dcc_type": "touchdesigner",
            "verb": args.command,
            "adapter_version": __version__,
            "core_version": runtime_core_version(),
            "steps": [],
            "next_steps": next_steps,
            "receipt_path": str(receipt_path()),
            "verify": empty_verify(),
            "failure": {"stage": exc.stage, "reason": exc.reason},
        }
        if args.as_json:
            print(json.dumps(report, sort_keys=True))
        else:
            print(f"{args.command}: {report['status']} ({exc.reason})")
        return exc.exit_code
    report.pop("_artifacts", None)
    if args.as_json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"{args.command}: {report['status']}")
    return EXIT_REQUIRES_RESTART if report["status"] == "requires_restart" else 0


if __name__ == "__main__":
    raise SystemExit(main())
