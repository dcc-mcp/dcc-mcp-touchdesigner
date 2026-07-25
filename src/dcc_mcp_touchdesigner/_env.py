"""Environment-variable resolution for ``TouchDesignerMcpServer``.

Centralises every ``DCC_MCP_TOUCHDESIGNER_*`` env var used by the server.
All helpers are pure functions: they read :data:`os.environ` and return
plain Python values; they never mutate global state.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Public env-var names ─────────────────────────────────────────────────
ENV_METRICS = "DCC_MCP_TOUCHDESIGNER_METRICS"
ENV_JOB_STORAGE = "DCC_MCP_TOUCHDESIGNER_JOB_STORAGE"
ENV_ENABLE_WORKFLOWS = "DCC_MCP_TOUCHDESIGNER_ENABLE_WORKFLOWS"
ENV_ENABLE_GATEWAY_FAILOVER = "DCC_MCP_TOUCHDESIGNER_ENABLE_GATEWAY_FAILOVER"
ENV_DISABLE_EXECUTE_PYTHON = "DCC_MCP_TOUCHDESIGNER_DISABLE_EXECUTE_PYTHON"
ENV_DISABLE_ARBITRARY_SCRIPT = "DCC_MCP_TOUCHDESIGNER_DISABLE_ARBITRARY_SCRIPT"
ENV_READINESS_TIMEOUT_SECS = "DCC_MCP_TOUCHDESIGNER_READINESS_TIMEOUT_SECS"
ENV_PROJECT_TOOLS = "DCC_MCP_TOUCHDESIGNER_PROJECT_TOOLS"
ENV_RESOURCES = "DCC_MCP_TOUCHDESIGNER_RESOURCES"

_TRUTHY = ("1", "true", "yes", "on")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def _resolve_opt_out(env_name: str, flag: Optional[bool]) -> bool:
    """Resolve an opt-out flag: explicit arg > env (``"0"`` disables) > ``True``."""
    if flag is not None:
        return bool(flag)
    raw = os.environ.get(env_name)
    if raw is None:
        return True
    return raw.strip() != "0"


def resolve_execute_python_disabled() -> bool:
    """Return True when ``execute_python`` must refuse all calls."""
    if _env_truthy(ENV_DISABLE_ARBITRARY_SCRIPT):
        return True
    return _env_truthy(ENV_DISABLE_EXECUTE_PYTHON)


def resolve_metrics_enabled(metrics_enabled: Optional[bool]) -> bool:
    if metrics_enabled is not None:
        return bool(metrics_enabled)
    return os.environ.get(ENV_METRICS, "").strip() == "1"


def resolve_job_storage(job_storage_path: Optional[str]) -> Optional[str]:
    if job_storage_path is not None:
        return job_storage_path
    env_path = os.environ.get(ENV_JOB_STORAGE, "").strip()
    if env_path:
        return env_path
    return None


def resolve_enable_workflows(enable_workflows: Optional[bool] = None) -> bool:
    if enable_workflows is not None:
        return bool(enable_workflows)
    return _env_truthy(ENV_ENABLE_WORKFLOWS)


def resolve_enable_gateway_failover(enable_gateway_failover: Optional[bool]) -> bool:
    if enable_gateway_failover is not None:
        return bool(enable_gateway_failover)
    if os.environ.get(ENV_ENABLE_GATEWAY_FAILOVER, "").strip():
        return _env_truthy(ENV_ENABLE_GATEWAY_FAILOVER)
    return True


def resolve_readiness_timeout_secs(readiness_timeout_secs: Optional[int] = None) -> Optional[int]:
    if readiness_timeout_secs is not None:
        try:
            val = int(readiness_timeout_secs)
        except (TypeError, ValueError):
            return None
        return val if val > 0 else None
    raw = os.environ.get(ENV_READINESS_TIMEOUT_SECS)
    if not raw or not raw.strip():
        return None
    try:
        val = int(raw.strip())
    except ValueError:
        logger.warning(
            "Ignoring invalid %s=%r (expected positive integer seconds)",
            ENV_READINESS_TIMEOUT_SECS,
            raw,
        )
        return None
    return val if val > 0 else None


def resolve_project_tools_enabled(flag: Optional[bool] = None) -> bool:
    return _resolve_opt_out(ENV_PROJECT_TOOLS, flag)


def resolve_resources_enabled(flag: Optional[bool] = None) -> bool:
    return _resolve_opt_out(ENV_RESOURCES, flag)
