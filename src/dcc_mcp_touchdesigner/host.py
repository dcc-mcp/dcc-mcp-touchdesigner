"""TouchDesigner host adapter for dcc-mcp-core main-thread dispatch.

TouchDesigner runs most operations on its main thread. The ``td`` module
is always available inside TouchDesigner's Python environment. Use
``td.timer`` for periodic callbacks (equivalent to Blender's ``bpy.app.timers``).
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

from dcc_mcp_core import HostUiDispatcherBase
from dcc_mcp_core.host import BlockingDispatcher, HostAdapter, QueueDispatcher

TickFn = Callable[[], Optional[float]]


@dataclass
class TouchDesignerTimerPumpStats:
    """Runtime counters for the TouchDesigner timer pump."""

    ticks: int = 0
    overrun_cycles: int = 0
    last_tick_ms: float = 0.0


class TouchDesignerTimerPump:
    """Small adapter around ``td.timer``.

    Core owns dispatcher queue semantics. This class owns only TouchDesigner's
    timer primitive so future core pump abstractions can replace it cleanly.

    TouchDesigner's ``td.timer.callback`` takes a callable and a delay in
    milliseconds. Setting delay to 0 schedules the callback as soon as possible
    on the main thread.
    """

    def __init__(self, budget_ms: float = 200.0) -> None:
        if budget_ms <= 0:
            raise ValueError("budget_ms must be > 0")
        self.budget_ms = float(budget_ms)
        self.stats = TouchDesignerTimerPumpStats()
        self._tick_fn: Optional[TickFn] = None
        self._registered_fn: Optional[Callable[[], None]] = None
        self._tick_thread_ident: Optional[int] = None
        self._running = False

    @property
    def tick_thread_ident(self) -> Optional[int]:
        """Thread id of the most recent TouchDesigner timer callback."""
        return self._tick_thread_ident

    @property
    def is_installed(self) -> bool:
        """Return whether a timer callback is currently registered."""
        return self._running

    def install(self, tick_fn: TickFn) -> None:
        """Register ``tick_fn`` with TouchDesigner's timer API."""
        if self._running:
            self._tick_fn = tick_fn
            return

        import td

        self._tick_fn = tick_fn
        self._running = True

        def _tick_wrapper() -> None:
            self._tick_thread_ident = threading.get_ident()
            start = time.monotonic()
            try:
                if self._tick_fn is None:
                    return
                delay_ms = self._tick_fn()
                if delay_ms is not None and self._running:
                    td.timer.callback(_tick_wrapper, delay_ms=int(delay_ms * 1000))
            finally:
                elapsed_ms = (time.monotonic() - start) * 1000.0
                self.stats.ticks += 1
                self.stats.last_tick_ms = elapsed_ms
                if elapsed_ms > self.budget_ms:
                    self.stats.overrun_cycles += 1

        td.timer.callback(_tick_wrapper, delay_ms=0)

    def uninstall(self) -> None:
        """Mark the pump as uninstalled."""
        self._running = False
        self._tick_fn = None

    def pumped_ms(self) -> float:
        """Return the most recent timer tick duration in milliseconds."""
        return self.stats.last_tick_ms

    def pump_count(self) -> int:
        """Return the number of timer ticks."""
        return self.stats.ticks

    def reset_stats(self) -> None:
        """Reset timer-pump counters."""
        self.stats.ticks = 0
        self.stats.overrun_cycles = 0
        self.stats.last_tick_ms = 0.0


class TouchDesignerUiDispatcher(HostUiDispatcherBase):
    """Core-backed dispatcher for TouchDesigner interactive UI mode."""

    def __init__(
        self,
        *,
        timeout_ms: int = 30000,
        budget_ms: float = 200.0,
        active_interval_secs: float = 0.0,
        idle_interval_secs: float = 0.5,
        pump: Optional[TouchDesignerTimerPump] = None,
    ) -> None:
        super().__init__()
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be > 0")
        if active_interval_secs < 0:
            raise ValueError("active_interval_secs must be >= 0")
        if idle_interval_secs <= 0:
            raise ValueError("idle_interval_secs must be > 0")
        self.timeout_ms = int(timeout_ms)
        self.budget_ms = float(budget_ms)
        self.active_interval_secs = float(active_interval_secs)
        self.idle_interval_secs = float(idle_interval_secs)
        self._pump = pump or TouchDesignerTimerPump(budget_ms=budget_ms)
        self._host_dispatcher = QueueDispatcher()
        self._owner_thread_ident = threading.get_ident()

    @property
    def host_dispatcher(self) -> QueueDispatcher:
        """Expose the core dispatcher that backs HTTP main-thread routing."""
        return self._host_dispatcher

    @property
    def pump(self) -> TouchDesignerTimerPump:
        """Return the TouchDesigner timer pump used by this dispatcher."""
        return self._pump

    def start(self) -> None:
        """Install the TouchDesigner timer pump."""
        self.start_pump()

    def stop(self) -> None:
        """Shutdown queued work and uninstall the TouchDesigner timer pump."""
        self.shutdown()
        self.stop_pump()

    def start_pump(self) -> None:
        """Ensure TouchDesigner timers are draining the core UI dispatcher queue."""
        self._pump.install(self._timer_tick)

    def stop_pump(self) -> None:
        """Detach the TouchDesigner timer pump."""
        self._pump.uninstall()

    def poke_host_pump(self) -> None:
        """Nudge TouchDesigner to drain queued main-thread work soon."""
        self.start_pump()

    def active_count(self) -> int:
        """Return the number of currently executing main-thread jobs."""
        with self._lock:
            return len(self._active)

    def shutdown(self, reason: str = "Interrupted") -> int:
        """Shutdown queued work and the underlying core dispatcher."""
        self._host_dispatcher.shutdown()
        return super().shutdown(reason)

    def dispatch_callable(
        self,
        func: Callable[..., Any],
        *args: Any,
        affinity: str = "main",
        context: Any = None,
        action_name: str = "",
        skill_name: Optional[str] = None,
        execution: str = "sync",
        timeout_hint_secs: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        """Run ``func`` through the shared core UI dispatcher queue."""
        _ = (context, execution)
        affinity_norm = (affinity or "main").lower()
        if affinity_norm == "main" and threading.get_ident() == self._owner_thread_ident:
            return func(*args, **kwargs)

        request_id = self._request_id_for(func, action_name, skill_name)
        timeout_ms = self._timeout_ms_from_hint(timeout_hint_secs)

        def _invoke() -> Any:
            return func(*args, **kwargs)

        outcome = self.submit_callable(request_id, _invoke, affinity=affinity_norm, timeout_ms=timeout_ms)
        if outcome.get("success"):
            return outcome.get("output")
        raise RuntimeError(outcome.get("error") or "TouchDesigner UI dispatch failed")

    def _timer_tick(self) -> Optional[float]:
        if self.is_shutdown:
            return None
        self._host_dispatcher.tick(16)
        _executed, remaining = self.drain_queue(self.budget_ms)
        return self.active_interval_secs if remaining else self.idle_interval_secs

    def _timeout_ms_from_hint(self, timeout_hint_secs: Optional[int]) -> Optional[int]:
        if timeout_hint_secs is None or timeout_hint_secs <= 0:
            return self.timeout_ms
        return int(timeout_hint_secs) * 1000

    @staticmethod
    def _request_id_for(func: Callable[..., Any], action_name: str, skill_name: Optional[str]) -> str:
        label_parts = [part for part in (skill_name, action_name, getattr(func, "__name__", "")) if part]
        label = ".".join(label_parts) or "touchdesigner-call"
        return f"{label}:{uuid.uuid4().hex}"


class TouchDesignerCallableDispatcher:
    """Callable dispatcher driven by TouchDesigner's host tick loop."""

    def __init__(self, dispatcher: Optional[BlockingDispatcher] = None) -> None:
        self._dispatcher = dispatcher or BlockingDispatcher()

    @property
    def host_dispatcher(self) -> BlockingDispatcher:
        """Return the core dispatcher that backs HTTP main-thread routing."""
        return self._dispatcher

    def dispatch_callable(
        self,
        func: Callable[..., Any],
        *args: Any,
        affinity: str = "main",
        context: Any = None,
        action_name: str = "",
        skill_name: Optional[str] = None,
        execution: str = "sync",
        timeout_hint_secs: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        """Post ``func`` to TouchDesigner's main-thread queue and wait for its result."""
        _ = (affinity, context, action_name, skill_name, execution)

        def _invoke() -> Any:
            return func(*args, **kwargs)

        handle = self._dispatcher.post(_invoke)
        return handle.wait(timeout_hint_secs)

    def tick(self, max_jobs: int):
        """Drain queued callables from TouchDesigner's main thread."""
        return self._dispatcher.tick(max_jobs)

    def tick_blocking(self, max_jobs: int, timeout_ms: int):
        """Drain queued callables, blocking briefly while headless."""
        return self._dispatcher.tick_blocking(max_jobs, timeout_ms)

    def shutdown(self) -> None:
        """Stop accepting queued work."""
        self._dispatcher.shutdown()

    def is_shutdown(self) -> bool:
        """Return whether the underlying dispatcher is shut down."""
        return bool(self._dispatcher.is_shutdown())


class TouchDesignerInlineCallableDispatcher:
    """Callable bridge used after the core dispatcher owns the main-thread hop."""

    def __init__(self, host_dispatcher: Any) -> None:
        self._host_dispatcher = host_dispatcher

    def dispatch_callable(
        self,
        func: Callable[..., Any],
        *args: Any,
        affinity: str = "main",
        context: Any = None,
        action_name: str = "",
        skill_name: Optional[str] = None,
        execution: str = "sync",
        timeout_hint_secs: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute ``func`` inline once HTTP has dispatched onto TouchDesigner's thread."""
        _ = (affinity, context, action_name, skill_name, execution, timeout_hint_secs)
        return func(*args, **kwargs)

    def shutdown(self, reason: str = "Interrupted") -> Any:
        """Forward shutdown to the underlying host dispatcher when supported."""
        shutdown = getattr(self._host_dispatcher, "shutdown", None)
        if not callable(shutdown):
            return None
        try:
            return shutdown(reason)
        except TypeError:
            return shutdown()


class TouchDesignerHost(HostAdapter):
    """Drive a dcc-mcp-core dispatcher from TouchDesigner's main thread.

    TouchDesigner exposes ``td.timer`` as its native idle primitive. In
    interactive mode this adapter registers the core dispatcher tick with that
    timer API.
    """

    def __init__(self, dispatcher, **kwargs) -> None:
        super().__init__(dispatcher, name=kwargs.pop("name", "touchdesigner-host"), **kwargs)
        self._timer_pump = TouchDesignerTimerPump()

    @property
    def tick_thread_ident(self) -> Optional[int]:
        """Thread id of the most recent TouchDesigner timer tick."""
        return self._timer_pump.tick_thread_ident

    def is_background(self) -> bool:
        """TouchDesigner always runs in a GUI context."""
        return False

    def attach_tick(self, tick_fn: TickFn) -> None:
        """Register ``tick_fn`` with ``td.timer``."""
        self._timer_pump.install(tick_fn)

    def detach_tick(self) -> None:
        """Unregister the TouchDesigner timer tick."""
        self._timer_pump.uninstall()
