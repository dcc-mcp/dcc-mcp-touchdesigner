import json
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest


def _configure_preflight(tmp_path, monkeypatch):
    host = tmp_path / "TouchDesigner.2025.30000" / "bin" / "TouchDesigner.exe"
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        assert Path(command[0]) == Path(sys.executable)
        payload = {
            "python_version": "3.11.10",
            "dcc-mcp-core": "0.20.8",
            "dcc-mcp-touchdesigner": "0.1.1",
            "site_packages": str(tmp_path / "venv" / "Lib" / "site-packages"),
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return host


def test_install_dry_run_plans_existing_release_bootstrap_without_writes(tmp_path, monkeypatch, capsys):
    from dcc_mcp_touchdesigner import cli

    host = _configure_preflight(tmp_path, monkeypatch)
    code = cli.main(
        [
            "install",
            "--dry-run",
            "--json",
            "--dcc-path",
            str(host),
            "--python",
            sys.executable,
        ]
    )

    report = json.loads(capsys.readouterr().out)
    stage = next(step for step in report["steps"] if step["id"] == "stage-bootstrap")
    assert code == 0
    assert report["schema_version"] == 1
    assert report["status"] == "planned"
    assert report["dcc_type"] == "touchdesigner"
    assert report["touchdesigner_version"] == "2025.30000"
    assert report["python_version"] == "3.11.10"
    assert stage["status"] == "planned"
    assert stage["source"] == "release-bootstrap"
    assert stage["bootstrap_sha256"]
    assert Path(stage["execute_dat_file"]).exists() is False
    assert len(report["next_steps"]) == 1
    assert report["next_steps"][0]["file_edit"]["path"].startswith("touchdesigner://")
    assert "onStart" in report["next_steps"][0]["file_edit"]["content"]
    assert Path(report["receipt_path"]).exists() is False


def test_install_stages_bootstrap_and_receipt_idempotently(tmp_path, monkeypatch, capsys):
    from dcc_mcp_touchdesigner import cli

    host = _configure_preflight(tmp_path, monkeypatch)
    arguments = [
        "install",
        "--yes",
        "--json",
        "--dcc-path",
        str(host),
        "--python",
        sys.executable,
    ]

    assert cli.main(arguments) == 50
    first = json.loads(capsys.readouterr().out)
    assert cli.main(arguments) == 50
    second = json.loads(capsys.readouterr().out)

    stage = next(step for step in first["steps"] if step["id"] == "stage-bootstrap")
    bootstrap = Path(stage["bootstrap_file"])
    execute_dat = Path(stage["execute_dat_file"])
    receipt = Path(first["receipt_path"])
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert first["status"] == "requires_restart"
    assert second["status"] == "requires_restart"
    assert bootstrap.is_file()
    assert execute_dat.is_file()
    assert "start_server" in bootstrap.read_text(encoding="utf-8")
    assert execute_dat.read_text(encoding="utf-8") == first["next_steps"][0]["file_edit"]["content"]
    assert receipt_payload["owner"] == "dcc-mcp-touchdesigner"
    assert receipt_payload["files"][0]["sha256"]
    assert receipt_payload["dcc_path"] == str(host.resolve())
    assert second["installation_state"] == "current"


def test_status_distinguishes_repair_from_stale_version(tmp_path, monkeypatch, capsys):
    from dcc_mcp_touchdesigner import cli

    host = _configure_preflight(tmp_path, monkeypatch)
    arguments = [
        "install",
        "--yes",
        "--json",
        "--dcc-path",
        str(host),
        "--python",
        sys.executable,
    ]
    assert cli.main(arguments) == 50
    installed = json.loads(capsys.readouterr().out)
    stage = next(step for step in installed["steps"] if step["id"] == "stage-bootstrap")
    bootstrap = Path(stage["bootstrap_file"])
    receipt = Path(installed["receipt_path"])

    bootstrap.write_text("tampered", encoding="utf-8")
    assert cli.main(["status", "--json"]) == 0
    repair = json.loads(capsys.readouterr().out)
    assert repair["installation_state"] == "repair"
    assert repair["checks"]["artifact_hashes_match"] is False

    assert cli.main(arguments) == 50
    capsys.readouterr()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["adapter_version"] = "0.1.0"
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    assert cli.main(["status", "--json"]) == 0
    upgrade = json.loads(capsys.readouterr().out)
    assert upgrade["installation_state"] == "upgrade"
    assert upgrade["checks"]["artifact_hashes_match"] is True
    assert upgrade["checks"]["version_stamp_current"] is False


def test_status_and_uninstall_are_receipt_driven(tmp_path, monkeypatch, capsys):
    from dcc_mcp_touchdesigner import cli

    host = _configure_preflight(tmp_path, monkeypatch)
    install_arguments = [
        "install",
        "--yes",
        "--json",
        "--dcc-path",
        str(host),
        "--python",
        sys.executable,
    ]
    assert cli.main(install_arguments) == 50
    installed = json.loads(capsys.readouterr().out)
    receipt = Path(installed["receipt_path"])
    stage = next(step for step in installed["steps"] if step["id"] == "stage-bootstrap")
    artifacts = [Path(stage["bootstrap_file"]), Path(stage["execute_dat_file"])]

    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("status and uninstall must not launch host or Python")

    monkeypatch.setattr(subprocess, "run", unexpected_run)
    assert cli.main(["status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "ok"
    assert status["installation_state"] == "current"
    assert status["checks"]["artifact_hashes_match"] is True

    assert cli.main(["uninstall", "--yes", "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert cli.main(["uninstall", "--yes", "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["status"] == "ok"
    assert first["installation_state"] == "fresh"
    assert second["status"] == "ok"
    assert receipt.exists() is False
    assert all(path.exists() is False for path in artifacts)


def test_verify_reaches_target_import_and_typed_readiness(tmp_path, monkeypatch, capsys):
    from dcc_mcp_touchdesigner import cli, install_lifecycle

    host = _configure_preflight(tmp_path, monkeypatch)
    assert (
        cli.main(
            [
                "install",
                "--yes",
                "--json",
                "--dcc-path",
                str(host),
                "--python",
                sys.executable,
            ]
        )
        == 50
    )
    capsys.readouterr()
    readiness_calls = []

    def import_check(command, **_kwargs):
        assert "import dcc_mcp_touchdesigner" in command[-1]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"success": True, "version": "0.1.1"}),
            stderr="",
        )

    def ready(**kwargs):
        readiness_calls.append(kwargs)
        return {"success": True, "ready": True, "status": "ready"}

    monkeypatch.setattr(subprocess, "run", import_check)
    monkeypatch.setattr(install_lifecycle, "wait_for_sidecar_ready", ready)

    assert cli.main(["verify", "--json", "--timeout", "0.25"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verify"]["directly_usable"] is True
    assert report["verify"]["artifact"]["success"] is True
    assert report["verify"]["import"]["success"] is True
    assert report["verify"]["readiness"]["success"] is True
    assert readiness_calls == [
        {
            "dcc_type": "touchdesigner",
            "timeout_secs": 0.25,
            "probe_tool": "touchdesigner_scripting__get_project_info",
        }
    ]


def test_target_preflight_rejects_missing_site_packages(monkeypatch):
    from dcc_mcp_touchdesigner.install_contract import InstallFailure
    from dcc_mcp_touchdesigner.install_host import target_info

    payload = {
        "python_version": "3.11.10",
        "dcc-mcp-core": "0.20.8",
        "dcc-mcp-touchdesigner": "0.1.1",
        "site_packages": "",
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr=""),
    )

    with pytest.raises(InstallFailure, match="site-packages") as caught:
        target_info(Path(sys.executable))

    assert caught.value.stage == "python"
    assert caught.value.exit_code == 10


def test_target_preflight_reports_malformed_python_version(monkeypatch):
    from dcc_mcp_touchdesigner.install_contract import InstallFailure
    from dcc_mcp_touchdesigner.install_host import target_info

    payload = {
        "python_version": "unknown",
        "dcc-mcp-core": "0.20.8",
        "dcc-mcp-touchdesigner": "0.1.1",
        "site_packages": "site-packages",
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr=""),
    )

    with pytest.raises(InstallFailure, match="Python 3.11") as caught:
        target_info(Path(sys.executable))

    assert caught.value.stage == "python"
    assert caught.value.exit_code == 10


def test_target_preflight_reports_malformed_core_version(monkeypatch):
    from dcc_mcp_touchdesigner.install_contract import InstallFailure
    from dcc_mcp_touchdesigner.install_host import target_info

    payload = {
        "python_version": "3.11.10",
        "dcc-mcp-core": "unknown",
        "dcc-mcp-touchdesigner": "0.1.1",
        "site_packages": "site-packages",
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr=""),
    )

    with pytest.raises(InstallFailure, match="invalid version") as caught:
        target_info(Path(sys.executable))

    assert caught.value.stage == "core"
    assert caught.value.exit_code == 10


def test_macos_bundle_version_is_discovered_from_info_plist(tmp_path, monkeypatch):
    from dcc_mcp_touchdesigner.install_host import resolve_touchdesigner, touchdesigner_version

    application = tmp_path / "TouchDesigner.app"
    executable = application / "Contents" / "MacOS" / "TouchDesigner"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    with (application / "Contents" / "Info.plist").open("wb") as stream:
        plistlib.dump({"CFBundleShortVersionString": "2025.30000"}, stream)
    monkeypatch.delenv("DCC_MCP_TOUCHDESIGNER_VERSION", raising=False)

    assert resolve_touchdesigner(application) == executable.resolve()
    assert touchdesigner_version(executable) == "2025.30000"


def test_install_refuses_unowned_artifacts(tmp_path):
    from dcc_mcp_touchdesigner.install_contract import InstallFailure
    from dcc_mcp_touchdesigner.install_files import install_artifacts

    root = tmp_path / "integration"
    root.mkdir()
    (root / "bootstrap.py").write_text("user owned", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dcc_type": "touchdesigner",
                "owner": "dcc-mcp-touchdesigner",
                "integration_root": str(root),
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    report = {
        "integration_root": str(root),
        "receipt_path": str(receipt),
        "adapter_version": "0.1.1",
        "core_version": "0.20.8",
        "touchdesigner_version": "2025.30000",
        "dcc_path": "TouchDesigner.exe",
        "python": "python.exe",
        "site_packages": "site-packages",
    }

    with pytest.raises(InstallFailure, match="unowned") as caught:
        install_artifacts(report, {"bootstrap.py": "managed", "execute_dat.py": "managed"})

    assert caught.value.stage == "ownership"
    assert (root / "bootstrap.py").read_text(encoding="utf-8") == "user owned"
    assert not (root / "execute_dat.py").exists()


def test_failed_upgrade_restores_previous_artifacts_and_receipt(tmp_path, monkeypatch):
    from dcc_mcp_touchdesigner import install_files
    from dcc_mcp_touchdesigner.install_contract import InstallFailure

    root = tmp_path / "integration"
    receipt = tmp_path / "receipt.json"
    report = {
        "integration_root": str(root),
        "receipt_path": str(receipt),
        "adapter_version": "0.1.1",
        "core_version": "0.20.8",
        "touchdesigner_version": "2025.30000",
        "dcc_path": "TouchDesigner.exe",
        "python": "python.exe",
        "site_packages": "site-packages",
    }
    previous = {"bootstrap.py": "old bootstrap", "execute_dat.py": "old execute"}
    install_files.install_artifacts(report, previous)
    receipt_before = receipt.read_bytes()
    real_atomic_write = install_files.atomic_write
    failed = False

    def fail_second_artifact(path, payload, mode=0o600):
        nonlocal failed
        if path.name == "execute_dat.py" and payload == b"new execute" and not failed:
            failed = True
            raise OSError("simulated staged replace failure")
        return real_atomic_write(path, payload, mode)

    monkeypatch.setattr(install_files, "atomic_write", fail_second_artifact)
    with pytest.raises(InstallFailure, match="simulated staged replace failure"):
        install_files.install_artifacts(
            report,
            {"bootstrap.py": "new bootstrap", "execute_dat.py": "new execute"},
        )

    assert (root / "bootstrap.py").read_text(encoding="utf-8") == "old bootstrap"
    assert (root / "execute_dat.py").read_text(encoding="utf-8") == "old execute"
    assert receipt.read_bytes() == receipt_before


def test_locked_install_returns_one_machine_executable_retry(tmp_path, monkeypatch, capsys):
    from dcc_mcp_touchdesigner import cli, install_lifecycle
    from dcc_mcp_touchdesigner.install_contract import EXIT_REQUIRES_RESTART, InstallFailure

    host = _configure_preflight(tmp_path, monkeypatch)

    def locked(*_args, **_kwargs):
        raise InstallFailure(EXIT_REQUIRES_RESTART, "artifact_locked", "bootstrap is locked")

    monkeypatch.setattr(install_lifecycle, "install_artifacts", locked)
    code = cli.main(
        [
            "install",
            "--yes",
            "--json",
            "--dcc-path",
            str(host),
            "--python",
            sys.executable,
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert code == 50
    assert report["status"] == "requires_restart"
    assert report["failure"]["stage"] == "artifact_locked"
    assert len(report["next_steps"]) == 1
    retry = report["next_steps"][0]
    assert retry["command"][0:2] == ["dcc-mcp-touchdesigner", "install"]
    assert "--yes" in retry["command"]


def test_rendered_bootstrap_records_startup_failure(tmp_path, monkeypatch):
    from dcc_mcp_touchdesigner.bootstrap import bootstrap_error_summary, render_bootstrap

    log = tmp_path / "bootstrap.jsonl"
    monkeypatch.setenv("DCC_MCP_TOUCHDESIGNER_BOOTSTRAP_ERROR_LOG", str(log))
    bootstrap = render_bootstrap(repr(str(tmp_path / "missing-adapter")))

    with pytest.raises(RuntimeError, match="adapter path not found"):
        exec(compile(bootstrap, "bootstrap.py", "exec"), {})

    summary = bootstrap_error_summary()
    assert summary["records_read"] == 1
    assert summary["last"]["success"] is False
    assert summary["last"]["stage"] == "initialize"
    assert summary["last"]["exception_type"] == "RuntimeError"
