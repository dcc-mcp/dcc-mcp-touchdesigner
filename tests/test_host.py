"""Host-thread scheduling contract tests."""

from __future__ import annotations

import sys
from types import SimpleNamespace


class _FakeRun:
    def __init__(self, callback, kwargs):
        self.callback = callback
        self.kwargs = kwargs
        self.killed = False

    def kill(self) -> None:
        self.killed = True


class _FakeTd:
    def __init__(self) -> None:
        self.op = SimpleNamespace(TDResources=object())
        self.runs: list[_FakeRun] = []

    def run(self, callback, **kwargs):
        handle = _FakeRun(callback, kwargs)
        self.runs.append(handle)
        return handle


def test_timer_pump_uses_cancellable_td_run(monkeypatch):
    from dcc_mcp_touchdesigner.host import TouchDesignerTimerPump

    td = _FakeTd()
    monkeypatch.setitem(sys.modules, "td", td)
    pump = TouchDesignerTimerPump()

    pump.install(lambda: 0.25)

    assert pump.is_installed
    assert len(td.runs) == 1
    assert td.runs[0].kwargs == {
        "endFrame": True,
        "group": "dcc-mcp-touchdesigner-pump",
    }

    td.runs[0].callback()

    assert pump.pump_count() == 1
    assert len(td.runs) == 2
    assert td.runs[1].kwargs["delayMilliSeconds"] == 250
    assert td.runs[1].kwargs["wallTime"] is True
    assert td.runs[1].kwargs["delayRef"] is td.op.TDResources

    pending = td.runs[1]
    pump.uninstall()

    assert not pump.is_installed
    assert pending.killed


def test_timer_pump_install_is_idempotent(monkeypatch):
    from dcc_mcp_touchdesigner.host import TouchDesignerTimerPump

    td = _FakeTd()
    monkeypatch.setitem(sys.modules, "td", td)
    pump = TouchDesignerTimerPump()

    pump.install(lambda: 0.5)
    pump.install(lambda: None)

    assert len(td.runs) == 1
    td.runs[0].callback()
    assert len(td.runs) == 1
