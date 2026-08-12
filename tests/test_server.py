"""Tests for TouchDesignerMcpServer and module-level helpers."""

from __future__ import annotations

import tempfile
from unittest.mock import patch

# ── helpers ───────────────────────────────────────────────────────────────────


def _builtin_skills_dir() -> str:
    from pathlib import Path

    return str(Path(__file__).parent.parent / "src" / "dcc_mcp_touchdesigner" / "skills")


# ── TouchDesignerMcpServer unit tests ─────────────────────────────────────────


class TestTouchDesignerMcpServerBasic:
    def test_instantiation(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert server is not None

    def test_default_port(self):
        from dcc_mcp_touchdesigner.server import DEFAULT_PORT, TouchDesignerMcpServer

        server = TouchDesignerMcpServer()
        assert server.port == DEFAULT_PORT

    def test_explicit_zero_port_overrides_environment(self, monkeypatch):
        from dcc_mcp_touchdesigner.server import TouchDesignerServerOptions

        monkeypatch.setenv("DCC_MCP_TOUCHDESIGNER_PORT", "18765")
        assert TouchDesignerServerOptions(port=0).to_core_options().port == 0

    def test_core_options_identify_gui_adapter_and_current_process(self):
        import os

        from dcc_mcp_touchdesigner.server import SERVER_VERSION, TouchDesignerServerOptions

        options = TouchDesignerServerOptions(port=0).to_core_options()

        assert options.instance_type == "gui"
        assert options.diagnostics.dcc_pid == os.getpid()
        assert options.sidecar.adapter_version == SERVER_VERSION
        assert options.observability.enable_job_persistence is True

    def test_custom_port(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=19999)
        assert server.port == 19999

    def test_extra_skill_paths_stored(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(extra_skill_paths=["/tmp/extra"])
        assert "/tmp/extra" in server._extra_skill_paths

    def test_not_running_initially(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer()
        assert not server.is_running

    def test_mcp_url_none_when_not_running(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer()
        assert server.mcp_url is None

    def test_dispatcher_is_wrapped_as_execution_bridge(self):
        from dcc_mcp_touchdesigner.host import (
            TouchDesignerCallableDispatcher,
            TouchDesignerInlineCallableDispatcher,
        )
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        dispatcher = TouchDesignerCallableDispatcher()
        server = TouchDesignerMcpServer(port=0, dispatcher=dispatcher)

        mode = server._options.execution.mode
        assert getattr(mode, "kind", None) == "bridge"
        assert isinstance(mode.bridge.dispatcher, TouchDesignerInlineCallableDispatcher)
        assert mode.bridge.host_dispatcher is dispatcher.host_dispatcher
        assert mode.bridge.dispatch_callable(lambda: "ok") == "ok"

    def test_core_backed_ui_dispatcher_is_used_as_execution_bridge(self):
        from dcc_mcp_touchdesigner.host import (
            TouchDesignerInlineCallableDispatcher,
            TouchDesignerUiDispatcher,
        )
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        dispatcher = TouchDesignerUiDispatcher()
        server = TouchDesignerMcpServer(port=0, dispatcher=dispatcher)

        mode = server._options.execution.mode
        assert getattr(mode, "kind", None) == "bridge"
        assert isinstance(mode.bridge.dispatcher, TouchDesignerInlineCallableDispatcher)
        assert mode.bridge.host_dispatcher is dispatcher.host_dispatcher
        assert mode.bridge.dispatch_callable(lambda: "ok", thread_affinity="main") == "ok"

    def test_explicit_execution_bridge_takes_precedence(self):
        from dcc_mcp_core import HostExecutionBridge

        from dcc_mcp_touchdesigner.host import TouchDesignerCallableDispatcher
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        dispatcher = TouchDesignerCallableDispatcher()
        bridge = HostExecutionBridge(dispatcher=dispatcher)
        server = TouchDesignerMcpServer(
            port=0,
            dispatcher=TouchDesignerCallableDispatcher(),
            execution_bridge=bridge,
        )

        mode = server._options.execution.mode
        assert getattr(mode, "kind", None) == "bridge"
        assert mode.bridge is bridge


class TestSkillPathCollection:
    """_collect_skill_paths respects all path sources."""

    def test_builtin_always_included(self):
        from dcc_mcp_touchdesigner.server import _BUILTIN_SKILLS_DIR, TouchDesignerMcpServer

        server = TouchDesignerMcpServer()
        paths = server._collect_skill_paths()
        assert str(_BUILTIN_SKILLS_DIR) in paths

    def test_extra_paths_take_priority(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        with tempfile.TemporaryDirectory() as tmp:
            server = TouchDesignerMcpServer(extra_skill_paths=[tmp])
            paths = server._collect_skill_paths()
            assert paths[0] == tmp

    def test_env_var_touchdesigner_skill_paths(self):
        from dcc_mcp_touchdesigner.server import _ENV_EXTRA_SKILL_PATHS, TouchDesignerMcpServer

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {_ENV_EXTRA_SKILL_PATHS: tmp}):
                server = TouchDesignerMcpServer()
                paths = server._collect_skill_paths()
                assert tmp in paths

    def test_env_var_generic_skill_paths(self):
        from dcc_mcp_touchdesigner.server import _ENV_GENERIC_SKILL_PATHS, TouchDesignerMcpServer

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {_ENV_GENERIC_SKILL_PATHS: tmp}):
                server = TouchDesignerMcpServer()
                paths = server._collect_skill_paths()
                assert tmp in paths

    def test_nonexistent_paths_excluded(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(extra_skill_paths=["/nonexistent/path/xyz"])
        paths = server._collect_skill_paths()
        assert "/nonexistent/path/xyz" not in paths

    def test_no_duplicates(self):
        from dcc_mcp_touchdesigner.server import _BUILTIN_SKILLS_DIR, TouchDesignerMcpServer

        builtin = str(_BUILTIN_SKILLS_DIR)
        server = TouchDesignerMcpServer(extra_skill_paths=[builtin])
        paths = server._collect_skill_paths()
        assert paths.count(builtin) == 1


class TestServerLifecycle:
    """Start/stop lifecycle tests using a real McpHttpServer."""

    def test_start_and_stop_drive_source_ui_dispatcher(self):
        from dcc_mcp_touchdesigner.host import TouchDesignerUiDispatcher
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        class FakePump:
            def __init__(self):
                self.is_installed = False

            def install(self, _tick_fn):
                self.is_installed = True

            def uninstall(self):
                self.is_installed = False

        pump = FakePump()
        dispatcher = TouchDesignerUiDispatcher(pump=pump)
        server = TouchDesignerMcpServer(port=0, dispatcher=dispatcher)

        assert server._td_dispatcher is dispatcher
        server.start()
        try:
            assert pump.is_installed
        finally:
            server.stop()
        assert not pump.is_installed

    def test_start_and_stop(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        server.start()
        assert server.is_running
        url = server.mcp_url
        assert url is not None
        assert "http://127.0.0.1:" in url
        server.stop()
        assert not server.is_running

    def test_start_idempotent(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        server.start()
        port_before = server.port
        server.start()
        assert server.port == port_before
        server.stop()

    def test_stop_noop_when_not_running(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        server.stop()  # should not raise

    def test_port_updated_after_start(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        server.start()
        try:
            assert server.port != 0, "port should be updated to the assigned port"
            assert server.port > 0
        finally:
            server.stop()

    def test_mcp_url_contains_port(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        server.start()
        try:
            url = server.mcp_url
            assert str(server.port) in url
        finally:
            server.stop()


class TestProgressiveLoading:
    """Progressive skill loading API: discover_skills / load_skill / unload_skill."""

    def test_list_skills_returns_list_before_start(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert server.list_skills() == []

    def test_find_skills_returns_list_before_start(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert server.find_skills() == []

    def test_discover_skills_returns_zero_before_start(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert server.discover_skills() == 0

    def test_loaded_skill_count_before_start(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert server.loaded_skill_count() == 0

    def test_is_skill_loaded_before_start(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert not server.is_skill_loaded("touchdesigner-scripting")

    def test_load_skill_returns_false_when_not_discovered(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert server.load_skill("touchdesigner-scripting") is False

    def test_unload_skill_returns_false_when_not_discovered(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert server.unload_skill("touchdesigner-scripting") is False

    def test_list_skills_after_start(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        server.start()
        try:
            skills = server.list_skills()
            assert isinstance(skills, list)
        finally:
            server.stop()

    def test_find_skills_after_start(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        server.start()
        try:
            results = server.find_skills(dcc="touchdesigner")
            assert isinstance(results, list)
        finally:
            server.stop()

    # ── behaviour tests (mocked McpHttpServer) ─────────────────────────────

    def _make_server_with_mock(self, mock_inner):
        """Return a running TouchDesignerMcpServer whose inner _server is mock_inner."""
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        server.start()
        server._server = mock_inner
        return server

    def test_list_skills_returns_content(self):
        from unittest.mock import MagicMock

        fake_skills = [
            {"name": "touchdesigner-scripting", "loaded": True, "dcc": "touchdesigner"},
        ]
        mock_inner = MagicMock()
        mock_inner.list_skills.return_value = fake_skills

        server = self._make_server_with_mock(mock_inner)
        try:
            result = server.list_skills()
            assert result == fake_skills
            mock_inner.list_skills.assert_called_once_with(status=None)
        finally:
            server.stop()

    def test_list_skills_with_status_filter(self):
        from unittest.mock import MagicMock

        mock_inner = MagicMock()
        mock_inner.list_skills.return_value = [{"name": "touchdesigner-scripting", "loaded": True}]

        server = self._make_server_with_mock(mock_inner)
        try:
            server.list_skills(status="loaded")
            mock_inner.list_skills.assert_called_once_with(status="loaded")
        finally:
            server.stop()

    def test_load_skill_returns_actions_and_updates_state(self):
        from unittest.mock import MagicMock

        mock_inner = MagicMock()
        mock_inner.load_skill.return_value = ["touchdesigner_scripting__execute_python"]
        mock_inner.is_loaded.return_value = True

        server = self._make_server_with_mock(mock_inner)
        try:
            assert server.load_skill("touchdesigner-scripting") is True
            mock_inner.load_skill.assert_called_once_with("touchdesigner-scripting")
            assert server.is_skill_loaded("touchdesigner-scripting") is True
        finally:
            server.stop()

    def test_unload_skill_returns_count(self):
        from unittest.mock import MagicMock

        mock_inner = MagicMock()
        mock_inner.unload_skill.return_value = 5
        mock_inner.is_loaded.return_value = False

        server = self._make_server_with_mock(mock_inner)
        try:
            assert server.unload_skill("touchdesigner-scripting") is True
            mock_inner.unload_skill.assert_called_once_with("touchdesigner-scripting")
            assert server.is_skill_loaded("touchdesigner-scripting") is False
        finally:
            server.stop()

    def test_discover_skills_returns_count(self):
        from unittest.mock import MagicMock

        mock_inner = MagicMock()
        mock_inner.discover.return_value = 3

        server = self._make_server_with_mock(mock_inner)
        try:
            count = server.discover_skills()
            assert count == 3
        finally:
            server.stop()

    def test_loaded_skill_count(self):
        from unittest.mock import MagicMock

        mock_inner = MagicMock()
        mock_inner.loaded_count.return_value = 2

        server = self._make_server_with_mock(mock_inner)
        try:
            assert server.loaded_skill_count() == 2
            mock_inner.loaded_count.assert_called_once()
        finally:
            server.stop()

    def test_load_unload_round_trip(self):
        from unittest.mock import MagicMock

        loaded_state = {"touchdesigner-scripting": False}

        mock_inner = MagicMock()
        mock_inner.load_skill.side_effect = lambda name: (
            loaded_state.__setitem__(name, True) or ["action_a", "action_b"]
        )
        mock_inner.unload_skill.side_effect = lambda name: loaded_state.__setitem__(name, False) or 2
        mock_inner.is_loaded.side_effect = lambda name: loaded_state.get(name, False)
        mock_inner.loaded_count.side_effect = lambda: sum(loaded_state.values())

        server = self._make_server_with_mock(mock_inner)
        try:
            assert server.load_skill("touchdesigner-scripting") is True
            assert server.is_skill_loaded("touchdesigner-scripting") is True
            assert server.loaded_skill_count() == 1

            assert server.unload_skill("touchdesigner-scripting") is True
            assert server.is_skill_loaded("touchdesigner-scripting") is False
            assert server.loaded_skill_count() == 0

            server.load_skill("touchdesigner-scripting")
            assert server.is_skill_loaded("touchdesigner-scripting") is True
            assert server.loaded_skill_count() == 1
        finally:
            server.stop()


class TestModuleSingleton:
    """Module-level start_server / stop_server singleton pattern."""

    def setup_method(self):
        from dcc_mcp_touchdesigner import server as srv_mod

        srv_mod._server_instance = None

    def teardown_method(self):
        from dcc_mcp_touchdesigner import server as srv_mod

        if srv_mod._server_instance is not None:
            srv_mod.stop_server()

    def test_start_stop(self):
        from dcc_mcp_touchdesigner.server import get_server, start_server, stop_server

        server = start_server(port=0)
        assert server is not None
        assert get_server() is server
        stop_server()
        assert get_server() is None

    def test_start_idempotent(self):
        from dcc_mcp_touchdesigner.server import start_server, stop_server

        s1 = start_server(port=0)
        s2 = start_server(port=0)
        assert s1 is s2
        stop_server()

    def test_get_server_none_when_not_running(self):
        from dcc_mcp_touchdesigner.server import get_server

        assert get_server() is None

    def test_stop_noop_when_not_running(self):
        from dcc_mcp_touchdesigner.server import stop_server

        stop_server()
        stop_server()


class TestVersionDetection:
    """_version_string returns "unknown" outside TouchDesigner."""

    def test_version_unknown_outside_td(self):
        from dcc_mcp_touchdesigner.server import TouchDesignerMcpServer

        server = TouchDesignerMcpServer(port=0)
        assert server._version_string() == "unknown"
