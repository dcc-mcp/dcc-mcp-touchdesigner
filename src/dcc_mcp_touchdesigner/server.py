"""TouchDesigner MCP server — embeds a Streamable HTTP MCP server inside TouchDesigner.

Extends :class:`dcc_mcp_core.server_base.DccServerBase` with TouchDesigner-specific
skill path discovery and version detection.

All generic logic (skill registration, hot-reload, gateway failover,
action registry, lifecycle) is provided by the base class.

Usage (inside TouchDesigner Python console or startup script)::

    import dcc_mcp_touchdesigner

    # Start with an OS-assigned instance port and discover it through the gateway.
    server = dcc_mcp_touchdesigner.start_server()

    # Progressive loading — discover skills without loading them immediately
    n = server.discover_skills()
    server.load_skill("touchdesigner-scripting")

    dcc_mcp_touchdesigner.stop_server()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dcc_mcp_core import DccServerOptions, HostExecutionBridge
from dcc_mcp_core.server_base import DccServerBase

from dcc_mcp_touchdesigner import _env
from dcc_mcp_touchdesigner.__version__ import __version__
from dcc_mcp_touchdesigner.host import TouchDesignerInlineCallableDispatcher

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

SERVER_NAME = "dcc-mcp-touchdesigner"
SERVER_VERSION = __version__
DEFAULT_PORT = 0

# Built-in skills directory shipped with this package
_BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent / "skills"

# Environment variable for extra skill paths (colon/semicolon separated)
_ENV_EXTRA_SKILL_PATHS = "DCC_MCP_TOUCHDESIGNER_SKILL_PATHS"
_ENV_GENERIC_SKILL_PATHS = "DCC_MCP_SKILL_PATHS"

_DCC_NAME = "touchdesigner"


def _is_host_queue_dispatcher(dispatcher: Any) -> bool:
    """Return True for core QueueDispatcher / BlockingDispatcher-like objects."""
    return callable(getattr(dispatcher, "post", None)) and callable(getattr(dispatcher, "tick", None))


def _host_dispatcher_from(dispatcher: Any) -> Any | None:
    """Resolve the core host dispatcher hidden behind adapter wrappers."""
    if _is_host_queue_dispatcher(dispatcher):
        return dispatcher
    host_dispatcher = getattr(dispatcher, "host_dispatcher", None)
    if host_dispatcher is not None and _is_host_queue_dispatcher(host_dispatcher):
        return host_dispatcher
    return None


# ── options ─────────────────────────────────────────────────────────────────


@dataclass
class TouchDesignerServerOptions:
    """Adapter-local options for the dcc-mcp-core server contract."""

    port: Optional[int] = None
    extra_skill_paths: Optional[List[str]] = None
    server_name: str = SERVER_NAME
    server_version: str = SERVER_VERSION
    gateway_port: Optional[int] = None
    registry_dir: Optional[str] = None
    dcc_version: Optional[str] = None
    scene: Optional[str] = None
    enable_gateway_failover: Optional[bool] = None
    metrics_enabled: Optional[bool] = None
    job_storage_path: Optional[str] = None
    enable_workflows: Optional[bool] = None
    dcc_pid: Optional[int] = None
    dcc_window_title: Optional[str] = None
    dispatcher: Optional[Any] = None
    execution_bridge: Optional[Any] = None

    def to_core_options(self) -> DccServerOptions:
        """Convert to core DccServerOptions using from_env()."""
        dispatcher = self.dispatcher
        execution_bridge = self.execution_bridge
        if execution_bridge is None and dispatcher is not None:
            host_dispatcher = _host_dispatcher_from(dispatcher)
            bridge_dispatcher = (
                TouchDesignerInlineCallableDispatcher(host_dispatcher) if host_dispatcher is not None else dispatcher
            )
            execution_bridge = HostExecutionBridge(
                dispatcher=bridge_dispatcher,
                host_dispatcher=host_dispatcher,
                default_thread_affinity="main",
            )
            dispatcher = None
        elif execution_bridge is not None:
            dispatcher = None

        return DccServerOptions.from_env(
            dcc_name=_DCC_NAME,
            builtin_skills_dir=_BUILTIN_SKILLS_DIR,
            port=self.port,
            server_name=self.server_name,
            server_version=self.server_version,
            gateway_port=self.gateway_port,
            registry_dir=self.registry_dir,
            dcc_version=self.dcc_version,
            scene=self.scene,
            enable_gateway_failover=_env.resolve_enable_gateway_failover(self.enable_gateway_failover),
            enable_file_logging=True,
            enable_job_persistence=_env.resolve_job_storage(self.job_storage_path) is not None,
            enable_telemetry=True,
            dcc_pid=self.dcc_pid,
            dcc_window_title=self.dcc_window_title,
            dispatcher=dispatcher,
            execution_bridge=execution_bridge,
        )


# ── server class ─────────────────────────────────────────────────────────────


class TouchDesignerMcpServer(DccServerBase):
    """MCP server embedded inside TouchDesigner.

    Thin subclass of :class:`~dcc_mcp_core.server_base.DccServerBase`.
    All skill management, hot-reload, and gateway election logic is
    inherited.  This class adds only:

    - TouchDesigner built-in skills directory (``skills/``)
    - TouchDesigner version detection via ``td`` module
    - Progressive loading helpers: :meth:`discover_skills`, :meth:`loaded_skill_count`

    Multi-instance / gateway
    ------------------------
    Each TouchDesigner process binds an OS-assigned instance port and registers
    its exact endpoint with the stable local gateway.

    Progressive loading
    -------------------
    Skills can be discovered (metadata only, no Python import) and loaded
    on demand::

        server.discover_skills()
        server.load_skill("touchdesigner-scripting")
        server.unload_skill("touchdesigner-scripting")

    Attributes:
        port: TCP port the server is listening on (updated after :meth:`start`).
    """

    def __init__(
        self,
        port: Optional[int] = None,
        extra_skill_paths: Optional[List[str]] = None,
        server_name: str = SERVER_NAME,
        server_version: str = SERVER_VERSION,
        gateway_port: Optional[int] = None,
        registry_dir: Optional[str] = None,
        dcc_version: Optional[str] = None,
        scene: Optional[str] = None,
        enable_gateway_failover: Optional[bool] = None,
        metrics_enabled: Optional[bool] = None,
        job_storage_path: Optional[str] = None,
        enable_workflows: Optional[bool] = None,
        dispatcher: Optional[Any] = None,
        execution_bridge: Optional[Any] = None,
        options: Optional[TouchDesignerServerOptions] = None,
    ) -> None:
        if options is None:
            if dispatcher is None and execution_bridge is None:
                # Default to a UI dispatcher if none provided
                try:
                    from dcc_mcp_touchdesigner.host import TouchDesignerUiDispatcher

                    dispatcher = TouchDesignerUiDispatcher()
                except Exception as exc:
                    logger.debug("[%s] Failed to create default dispatcher: %s", _DCC_NAME, exc)

            options = TouchDesignerServerOptions(
                port=port,
                extra_skill_paths=extra_skill_paths,
                server_name=server_name,
                server_version=server_version,
                gateway_port=gateway_port,
                registry_dir=registry_dir,
                dcc_version=dcc_version,
                scene=scene,
                enable_gateway_failover=enable_gateway_failover,
                metrics_enabled=metrics_enabled,
                job_storage_path=job_storage_path,
                enable_workflows=enable_workflows,
                dispatcher=dispatcher,
                execution_bridge=execution_bridge,
            )

        super().__init__(options=options.to_core_options())

        self._extra_skill_paths: List[str] = list(options.extra_skill_paths or [])

        if _env.resolve_metrics_enabled(options.metrics_enabled):
            self._config.enable_prometheus = True
            logger.info("[%s] Prometheus /metrics endpoint enabled", _DCC_NAME)

        effective_job_path = _env.resolve_job_storage(options.job_storage_path)
        if effective_job_path:
            self._config.job_storage_path = effective_job_path
            logger.info("[%s] Job storage: %s", _DCC_NAME, effective_job_path)
        elif effective_job_path == "":
            self._config.job_storage_path = ""

        if _env.resolve_enable_workflows(options.enable_workflows):
            try:
                self._config.enable_workflows = True
                logger.info("[%s] Workflow engine enabled", _DCC_NAME)
            except Exception as exc:
                logger.warning("[%s] Could not enable workflows: %s", _DCC_NAME, exc)

        gateway_port_arg = options.gateway_port
        enable_gw = _env.resolve_enable_gateway_failover(options.enable_gateway_failover)
        if gateway_port_arg == 0 or (gateway_port_arg is None and not enable_gw):
            self._config.gateway_port = 0

        # Host dispatcher (if any) is owned by core's execution bridge
        self._td_dispatcher: Any = getattr(self, "_dcc_dispatcher", None)

    # ── TouchDesigner version detection ───────────────────────────────────

    def _version_string(self) -> str:
        """Return the TouchDesigner version via the ``td`` module."""
        try:
            import td

            return str(td.version)
        except ImportError:
            return "unknown"

    # ── Port property ─────────────────────────────────────────────────────

    @property
    def port(self) -> int:
        """TCP port the server is listening on."""
        if self._handle is not None:
            try:
                return int(self._handle.port)
            except Exception:
                pass
        return int(self._options.port)

    # ── Skill search path helpers ─────────────────────────────────────────

    def _collect_skill_paths(self) -> List[str]:
        """Collect and deduplicate existing skill paths."""
        return self.collect_skill_search_paths(
            extra_paths=self._extra_skill_paths,
            filter_existing=True,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self, *, install_atexit_hook: bool = True) -> "TouchDesignerMcpServer":
        """Start the MCP HTTP server and the attached host dispatcher.

        Returns *self* for chaining.
        """
        super().start(install_atexit_hook=install_atexit_hook)
        if self._td_dispatcher is not None:
            start_fn = getattr(self._td_dispatcher, "start", None)
            if callable(start_fn):
                start_fn()
        return self

    def stop(self) -> None:
        """Stop the HTTP server and the dispatcher."""
        super().stop()

        if self._td_dispatcher is not None:
            stop_fn = getattr(self._td_dispatcher, "stop", None)
            if callable(stop_fn):
                stop_fn()

    # ── Builtin action registration ───────────────────────────────────────

    def register_builtin_actions(
        self,
        extra_skill_paths: Optional[List[str]] = None,
        include_bundled: bool = True,
        minimal_mode: Any = None,
    ) -> "TouchDesignerMcpServer":
        """Discover skills and attach TouchDesigner-specific core integrations."""
        super().register_builtin_actions(
            extra_skill_paths=extra_skill_paths,
            include_bundled=include_bundled,
            minimal_mode=minimal_mode,
        )
        self._register_introspect_tools()
        return self

    def _register_introspect_tools(self) -> None:
        """Register the shared core ``dcc_introspect__*`` tools."""
        try:
            from dcc_mcp_core import register_introspect_tools

            register_introspect_tools(self._server, dcc_name=_DCC_NAME)
        except Exception as exc:
            logger.debug("[%s] introspect tools registration failed: %s", _DCC_NAME, exc)

    # ── Progressive skill loading ─────────────────────────────────────────

    def discover_skills(
        self,
        extra_paths: Optional[List[str]] = None,
    ) -> int:
        """Scan skill directories and register tool metadata without importing scripts.

        Args:
            extra_paths: Additional directories to scan beyond the configured paths.

        Returns:
            Number of newly discovered skills (0 if server is not running).
        """
        if self._handle is None:
            logger.warning("discover_skills called before server was started")
            return 0
        paths = self._collect_skill_paths()
        if extra_paths:
            paths = list(extra_paths) + paths
        count = self._server.discover(extra_paths=paths, dcc_name=_DCC_NAME)
        logger.debug("TouchDesignerMcpServer: discovered %d new skill(s)", count)
        return count

    def load_skill(self, skill_name: str) -> bool:
        """Load a skill by name.

        Args:
            skill_name: Skill name as declared in ``SKILL.md`` (e.g. ``"touchdesigner-scripting"``).

        Returns:
            ``True`` when the core server accepted the load request.
        """
        try:
            self._server.load_skill(skill_name)
        except Exception as exc:
            logger.debug("TouchDesignerMcpServer: load_skill(%r) failed: %s", skill_name, exc)
            return False
        return True

    def unload_skill(self, skill_name: str) -> bool:
        """Unload a skill, removing its tools from the registry.

        Args:
            skill_name: Skill name to unload.

        Returns:
            ``True`` when the core server accepted the unload request.
        """
        try:
            self._server.unload_skill(skill_name)
        except Exception as exc:
            logger.debug("TouchDesignerMcpServer: unload_skill(%r) failed: %s", skill_name, exc)
            return False
        return True

    def list_skills(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all discovered skills with their load status.

        Args:
            status: Optional filter — ``"loaded"`` or ``"unloaded"``.

        Returns:
            List of dicts with skill status information, or ``[]`` if not running.
        """
        if self._handle is None:
            return []
        return list(self._server.list_skills(status=status))

    def search_skills(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        dcc: Optional[str] = None,
        scope: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search for skills matching the given criteria.

        Args:
            query: Free-text query matched against skill name/description.
            tags: Required tags (skill must have all).
            dcc: DCC filter (defaults to ``"touchdesigner"``).
            scope: Optional skill scope filter.
            limit: Optional maximum number of results.

        Returns:
            List of matching skill metadata dicts, or ``[]`` if not running.
        """
        if self._handle is None:
            return []
        try:
            return list(
                self._server.search_skills(
                    query=query,
                    tags=tags or [],
                    dcc=dcc or _DCC_NAME,
                    scope=scope,
                    limit=limit,
                )
            )
        except Exception as exc:
            logger.debug("TouchDesignerMcpServer: search_skills failed: %s", exc)
            return []

    def find_skills(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        dcc: Optional[str] = None,
        scope: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Backward-compatible alias for :meth:`search_skills`."""
        return self.search_skills(query=query, tags=tags, dcc=dcc, scope=scope, limit=limit)

    def is_skill_loaded(self, skill_name: str) -> bool:
        """Return ``True`` if the named skill is currently loaded."""
        if self._handle is None:
            return False
        return self._server.is_loaded(skill_name)

    def loaded_skill_count(self) -> int:
        """Return the number of currently loaded skills."""
        if self._handle is None:
            return 0
        return self._server.loaded_count()


# ── module-level singleton helpers ────────────────────────────────────────────

_server_instance: Optional[TouchDesignerMcpServer] = None


def start_server(
    port: Optional[int] = None,
    extra_skill_paths: Optional[List[str]] = None,
    register_builtins: bool = True,
    include_bundled: bool = True,
    enable_hot_reload: bool = False,
    gateway_port: Optional[int] = None,
    registry_dir: Optional[str] = None,
    dcc_version: Optional[str] = None,
    scene: Optional[str] = None,
    enable_gateway_failover: Optional[bool] = None,
    metrics_enabled: Optional[bool] = None,
    job_storage_path: Optional[str] = None,
    enable_workflows: Optional[bool] = None,
    dispatcher: Optional[Any] = None,
    execution_bridge: Optional[Any] = None,
) -> TouchDesignerMcpServer:
    """Start the TouchDesigner MCP server (creates a process-level singleton).

    The first call creates and starts the server.  Subsequent calls return the
    existing instance without restarting it.

    Multi-instance support (gateway mode)
    --------------------------------------
    Every instance uses an OS-assigned port and registers with the gateway.

    Args:
        port: Explicit TCP port, or ``None`` to let core resolve the environment/default.
        extra_skill_paths: Additional skill directories beyond built-ins.
        register_builtins: If ``True``, discover and load all skills.
        include_bundled: Include dcc-mcp-core bundled skills.
        enable_hot_reload: Enable skill hot-reload on file changes.
        gateway_port: Gateway competition port.
        registry_dir: Shared registry directory.
        dcc_version: TouchDesigner version for gateway registry.
        scene: Currently open project file path for the gateway registry.
        enable_gateway_failover: Enable automatic gateway failover.
        metrics_enabled: Force Prometheus ``/metrics`` (``None`` = env).
        job_storage_path: SQLite job DB path (``None`` = env / default).
        enable_workflows: Enable workflow MCP tools (``None`` = env).
        dispatcher: Optional host dispatcher for main-thread execution.
        execution_bridge: Optional execution bridge supplied by dcc-mcp-core.

    Returns:
        The running :class:`TouchDesignerMcpServer` instance.
    """
    global _server_instance
    if _server_instance is not None and _server_instance.is_running:
        return _server_instance

    _server_instance = TouchDesignerMcpServer(
        port=port,
        extra_skill_paths=extra_skill_paths,
        gateway_port=gateway_port,
        registry_dir=registry_dir,
        dcc_version=dcc_version,
        scene=scene,
        enable_gateway_failover=enable_gateway_failover,
        metrics_enabled=metrics_enabled,
        job_storage_path=job_storage_path,
        enable_workflows=enable_workflows,
        dispatcher=dispatcher,
        execution_bridge=execution_bridge,
    )
    if register_builtins:
        _server_instance.register_builtin_actions(include_bundled=include_bundled)
    if enable_hot_reload:
        _server_instance.enable_hot_reload()
    _server_instance.start()
    return _server_instance


def stop_server() -> None:
    """Stop the running TouchDesigner MCP server."""
    global _server_instance
    if _server_instance is None:
        return
    _server_instance.stop()
    _server_instance = None


def get_server() -> Optional[TouchDesignerMcpServer]:
    """Return the current server instance, or ``None`` if not started."""
    return _server_instance
