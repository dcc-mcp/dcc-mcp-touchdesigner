"""Typed TouchDesigner operation contract tests with an in-memory host."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest


class _Parameter:
    def __init__(self, name: str, value):
        self.name = name
        self.label = name.title()
        self.default = value
        self.mode = "CONSTANT"
        self.val = value
        self.pulses = []

    def eval(self):
        return self.val

    def pulse(self, value=1, frames=0, seconds=0):
        self.pulses.append({"value": value, "frames": frames, "seconds": seconds})


class _ParameterCollection:
    def __init__(self, parameters):
        self._parameters = {parameter.name: parameter for parameter in parameters}

    def __getitem__(self, name):
        return self._parameters.get(name)


class _Connector:
    def __init__(self, owner=None, index: int = 0, description: str = ""):
        self.owner = owner
        self.index = index
        self.description = description
        self.target = None
        self.connections = []
        self.isInput = description == "input"
        self.isOutput = description == "output"

    def connect(self, target) -> None:
        self.target = target
        if self not in target.connections:
            target.connections.append(self)
        if target not in self.connections:
            self.connections.append(target)

    def disconnect(self) -> None:
        for connection in list(self.connections):
            if self in connection.connections:
                connection.connections.remove(self)
        self.connections.clear()
        self.target = None


class _ProxyingConnector(_Connector):
    """Model TouchDesigner returning a fresh Python wrapper for one connector."""

    def connect(self, target) -> None:
        proxy = _Connector(self.owner, self.index, self.description)
        target.connections.append(proxy)
        self.connections.append(target)


class _Operator:
    def __init__(self, name: str, path: str, op_type: str = "baseCOMP", family: str = "COMP"):
        self.name = name
        self.path = path
        self.OPType = op_type
        self.family = family
        self.children: list[_Operator] = []
        self.par = _ParameterCollection([_Parameter("gain", 1.0)])
        self.outputConnectors = [_Connector(self, 0, "output")]
        self.inputConnectors = [_Connector(self, 0, "input")]
        self.bypass = False
        self.display = True
        self.render = False
        self.lock = False
        self.viewer = False
        self.nodeX = 0
        self.nodeY = 0
        self.nodeWidth = 100
        self.nodeHeight = 100
        self.cookFrame = 100.0
        self.cookTime = 0.25
        self.destroyed = False

    def __str__(self) -> str:
        return self.path

    def pars(self):
        return list(self.par._parameters.values())

    def create(self, operator_type: str, name: Optional[str] = None):
        operator_name = name or f"{operator_type}1"
        family = operator_type[-3:].upper()
        child = _Operator(operator_name, f"{self.path.rstrip('/')}/{operator_name}", operator_type, family)
        self.children.append(child)
        return child

    def destroy(self) -> None:
        self.destroyed = True


class _Top(_Operator):
    width = 1280
    height = 720

    def save(self, path: str) -> None:
        Path(path).write_bytes(b"not-a-real-png-but-a-deterministic-host-artifact")


class _Dat(_Operator):
    def __init__(self, name: str, path: str, op_type: str = "textDAT"):
        super().__init__(name, path, op_type, "DAT")
        self.isText = op_type == "textDAT"
        self.isTable = op_type == "tableDAT"
        self.isEditable = True
        self.text = "初始内容"
        self.numRows = 1
        self.numCols = 1


class _Project:
    name = "demo.toe"
    folder = "C:/projects/demo"
    cookRate = 60.0
    realTime = True

    def save(self, path: str) -> bool:
        target = Path(path)
        target.write_bytes(b"touchdesigner-project")
        self.name = target.name
        self.folder = str(target.parent)
        return True


class _Td:
    def __init__(self) -> None:
        root = _Operator("root", "/")
        project = _Operator("project1", "/project1")
        top = _Top("noise1", "/project1/noise1", "noiseTOP", "TOP")
        text = _Dat("notes1", "/project1/notes1")
        root.time = SimpleNamespace(frame=1.0, seconds=0.0, play=True)
        root.children.append(project)
        project.children.extend((top, text))
        self._operators = {operator.path: operator for operator in (root, project, top, text)}
        self.project = _Project()
        self.app = SimpleNamespace(
            version="099",
            build="2025.33070",
            product="TouchDesigner",
            processId=4242,
        )

    def op(self, path: str):
        operator = self._operators.get(path)
        return None if operator is not None and operator.destroyed else operator


@pytest.fixture
def fake_td(monkeypatch):
    td = _Td()
    monkeypatch.setitem(sys.modules, "td", td)
    return td


def test_project_and_operator_inspection(fake_td):
    from dcc_mcp_touchdesigner.operations import (
        get_operator_parameters,
        get_project_info,
        inspect_operator,
        list_operators,
    )

    project = get_project_info()
    listing = list_operators("/", recurse=True, type_filter="TOP")
    parameters = get_operator_parameters("/project1/noise1", names=["gain", "missing"])
    inspected = inspect_operator("/project1/noise1")

    assert project["project_name"] == "demo.toe"
    assert "project_folder" not in project
    assert project["touchdesigner_version"] == "2025.33070"
    assert project["touchdesigner_generation"] == "099"
    assert project["touchdesigner_build"] == "2025.33070"
    assert listing["count"] == 1
    assert listing["operators"][0]["path"] == "/project1/noise1"
    assert parameters["parameters"]["gain"]["value"] == 1.0
    assert parameters["missing"] == ["missing"]
    assert inspected["operator"]["path"] == "/project1/noise1"
    assert inspected["flags"]["display"] is True
    assert inspected["cook"]["frame"] == 100.0


def test_create_connect_update_and_delete(fake_td):
    from dcc_mcp_touchdesigner.operations import (
        connect_operators,
        create_operator,
        delete_operator,
        disconnect_operator_input,
        inspect_connections,
        pulse_operator_parameter,
        set_operator_flags,
        set_operator_parameter,
    )

    created = create_operator("/project1", "levelTOP", "grade1")
    grade = fake_td._operators["/project1"].children[-1]
    fake_td._operators[grade.path] = grade
    connected = connect_operators("/project1/noise1", grade.path)
    connections = inspect_connections(grade.path)
    updated = set_operator_parameter(grade.path, "gain", 2.5)
    pulsed = pulse_operator_parameter(grade.path, "gain", value=2, frames=1)
    flags = set_operator_flags(grade.path, {"display": False, "render": True})
    disconnected = disconnect_operator_input(grade.path, input_index=0)
    deleted = delete_operator(grade.path)

    assert created["operator"]["path"] == "/project1/grade1"
    assert fake_td._operators["/project1/noise1"].outputConnectors[0].target is grade.inputConnectors[0]
    assert connected["input_index"] == 0
    assert connected["verified_connected"] is True
    assert connections["inputs"][0]["connections"][0]["path"] == "/project1/noise1"
    assert updated["value"] == 2.5
    assert pulsed["parameter"] == "gain"
    assert grade.par["gain"].pulses == [{"value": 2, "frames": 1, "seconds": 0.0}]
    assert flags["after"] == {"display": False, "render": True}
    assert disconnected["verified_disconnected"] is True
    assert deleted["deleted"]["path"] == grade.path
    assert grade.destroyed


def test_connect_accepts_equivalent_host_connector_proxy(fake_td):
    from dcc_mcp_touchdesigner.operations import connect_operators

    source = fake_td._operators["/project1/noise1"]
    target = fake_td._operators["/project1"]
    source.outputConnectors = [_ProxyingConnector(source, 0, "output")]

    connected = connect_operators(source.path, target.path)

    assert connected["verified_connected"] is True
    assert target.inputConnectors[0].connections[0] is not source.outputConnectors[0]


def test_operator_layout_is_bounded_atomic_and_verified(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, set_operator_layout

    operator = fake_td._operators["/project1/noise1"]

    update = set_operator_layout(operator.path, x=120, y=-40, width=180, height=90)

    assert update["before"] == {"x": 0, "y": 0, "width": 100, "height": 100}
    assert update["after"] == {"x": 120, "y": -40, "width": 180, "height": 90}
    with pytest.raises(TouchDesignerOperationError, match="at least one"):
        set_operator_layout(operator.path)
    with pytest.raises(TouchDesignerOperationError, match="x must be an integer"):
        set_operator_layout(operator.path, x=1.5)


def test_create_requires_host_registration_and_cleans_up_unverified_operator(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, create_operator

    parent = fake_td._operators["/project1"]
    orphan = _Operator("orphan1", "/project1/orphan1", "nullTOP", "TOP")
    parent.create = lambda *_args, **_kwargs: orphan

    with pytest.raises(TouchDesignerOperationError, match="did not register"):
        create_operator(parent.path, "nullTOP", "orphan1")

    assert orphan.destroyed


def test_failed_connection_readback_restores_the_previous_input(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, connect_operators

    target = _Operator("grade1", "/project1/grade1", "levelTOP", "TOP")
    previous = _Operator("constant1", "/project1/constant1", "constantTOP", "TOP")
    source = fake_td._operators["/project1/noise1"]
    fake_td._operators[target.path] = target
    fake_td._operators[previous.path] = previous
    previous.outputConnectors[0].connect(target.inputConnectors[0])

    class _UnverifiableConnector(_Connector):
        def connect(self, input_connector) -> None:
            input_connector.disconnect()
            self.target = input_connector

    source.outputConnectors[0] = _UnverifiableConnector(source, 0, "output")

    with pytest.raises(TouchDesignerOperationError, match="rolled back"):
        connect_operators(source.path, target.path)

    assert target.inputConnectors[0].connections == [previous.outputConnectors[0]]
    assert previous.outputConnectors[0].connections == [target.inputConnectors[0]]


def test_failed_disconnection_readback_restores_the_previous_input(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, disconnect_operator_input

    target = _Operator("grade1", "/project1/grade1", "levelTOP", "TOP")
    source = fake_td._operators["/project1/noise1"]
    fake_td._operators[target.path] = target

    class _FirstDisconnectIsIgnored(_Connector):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.disconnect_calls = 0

        def disconnect(self) -> None:
            self.disconnect_calls += 1
            if self.disconnect_calls > 1:
                super().disconnect()

    input_connector = _FirstDisconnectIsIgnored(target, 0, "input")
    target.inputConnectors[0] = input_connector
    source.outputConnectors[0].connect(input_connector)

    with pytest.raises(TouchDesignerOperationError, match="rolled back"):
        disconnect_operator_input(target.path)

    assert input_connector.connections == [source.outputConnectors[0]]
    assert source.outputConnectors[0].connections == [input_connector]


def test_failed_parameter_readback_restores_expression_mode(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, set_operator_parameter

    class _ExpressionParameter:
        name = "gain"
        label = "Gain"
        default = 1.0
        expr = "absTime.frame"
        bindExpr = ""

        def __init__(self) -> None:
            self._val = 1.0
            self.mode = "EXPRESSION"

        @property
        def val(self):
            return self._val

        @val.setter
        def val(self, value) -> None:
            self._val = value
            self.mode = "CONSTANT"

        def eval(self):
            if self._val == 2.5:
                raise RuntimeError("simulated TouchDesigner readback failure")
            return self._val

    parameter = _ExpressionParameter()
    fake_td._operators["/project1/noise1"].par = _ParameterCollection([parameter])

    with pytest.raises(TouchDesignerOperationError, match="rolled back"):
        set_operator_parameter("/project1/noise1", "gain", 2.5)

    assert parameter.val == 1.0
    assert parameter.expr == "absTime.frame"
    assert parameter.bindExpr == ""
    assert parameter.mode == "EXPRESSION"


def test_root_delete_and_existing_artifacts_are_rejected(fake_td, tmp_path):
    from dcc_mcp_touchdesigner.operations import (
        TouchDesignerOperationError,
        capture_top,
        delete_operator,
        save_project,
    )

    with pytest.raises(TouchDesignerOperationError, match="root"):
        delete_operator("/")

    capture = capture_top("/project1/noise1", str(tmp_path / "preview.png"))
    project = save_project(str(tmp_path / "demo.toe"))

    assert capture["width"] == 1280
    assert capture["bytes"] > 0
    assert len(capture["sha256"]) == 64
    assert project["bytes"] > 0
    assert len(project["sha256"]) == 64

    with pytest.raises(TouchDesignerOperationError, match="already exists"):
        capture_top("/project1/noise1", str(tmp_path / "preview.png"))
    with pytest.raises(TouchDesignerOperationError, match="already exists"):
        save_project(str(tmp_path / "demo.toe"))


def test_missing_operator_is_explicit(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, list_operators

    with pytest.raises(TouchDesignerOperationError, match="operator not found"):
        list_operators("/missing")


def test_operator_and_parameter_inspection_are_bounded(fake_td):
    from dcc_mcp_touchdesigner.operations import (
        TouchDesignerOperationError,
        get_operator_parameters,
        list_operators,
    )

    listing = list_operators("/", recurse=True, limit=1)
    assert listing["count"] == 1
    assert listing["truncated"] is True

    with pytest.raises(TouchDesignerOperationError, match="names"):
        get_operator_parameters("/project1/noise1", names=[f"p{index}" for index in range(257)])

    with pytest.raises(TouchDesignerOperationError, match="integer"):
        list_operators("/", limit=1.5)


def test_unicode_dat_content_uses_optimistic_concurrency(fake_td):
    from dcc_mcp_touchdesigner.operations import (
        TouchDesignerOperationError,
        get_dat_content,
        set_dat_content,
    )

    before = get_dat_content("/project1/notes1")
    arbitrary_unicode = "日本語 · العربية · Հայերեն · ქართული · አማርኛ · বাংলা · e\u0301 · 👩🏽‍💻 · 𐐷"
    updated = set_dat_content(
        "/project1/notes1",
        arbitrary_unicode,
        expected_sha256=before["sha256"],
    )
    after = get_dat_content("/project1/notes1")

    assert updated["before_sha256"] == before["sha256"]
    assert updated["after_sha256"] == after["sha256"]
    assert after["content"] == arbitrary_unicode

    with pytest.raises(TouchDesignerOperationError, match="changed"):
        set_dat_content("/project1/notes1", "stale", expected_sha256=before["sha256"])


def test_failed_dat_readback_restores_the_previous_content(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, set_dat_content

    class _NormalizingDat(_Dat):
        def __init__(self, name: str, path: str):
            self._text = ""
            super().__init__(name, path)

        @property
        def text(self):
            return self._text

        @text.setter
        def text(self, value):
            self._text = "host-normalized" if value == "requested" else value

    dat = _NormalizingDat("notes2", "/project1/notes2")
    fake_td._operators[dat.path] = dat

    with pytest.raises(TouchDesignerOperationError, match="restored"):
        set_dat_content(dat.path, "requested")

    assert dat.text == "初始内容"


def test_pulse_value_is_bounded_json(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, pulse_operator_parameter

    with pytest.raises(TouchDesignerOperationError, match="bounded JSON"):
        pulse_operator_parameter("/project1/noise1", "gain", value=object())

    with pytest.raises(TouchDesignerOperationError, match="bounded JSON"):
        pulse_operator_parameter("/project1/noise1", "gain", value=float("nan"))


def test_dat_write_rejects_executable_dat_types(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, set_dat_content

    execute_dat = _Dat("execute1", "/project1/execute1", "executeDAT")
    fake_td._operators[execute_dat.path] = execute_dat

    with pytest.raises(TouchDesignerOperationError, match="Text DAT or Table DAT"):
        set_dat_content(execute_dat.path, "print('must not run')")


def test_timeline_read_and_atomic_update(fake_td):
    from dcc_mcp_touchdesigner.operations import get_timeline_state, set_timeline_state

    before = get_timeline_state()
    update = set_timeline_state(frame=42.0, play=False, cook_rate=30.0, real_time=False)
    after = get_timeline_state()

    assert before == {"frame": 1.0, "seconds": 0.0, "play": True, "cook_rate": 60.0, "real_time": True}
    assert update["before"] == before
    assert update["after"] == after
    assert after["frame"] == 42.0
    assert after["play"] is False
    assert after["cook_rate"] == 30.0
    assert after["real_time"] is False


def test_timeline_pauses_before_frame_mutation_and_resumes_last(fake_td):
    from dcc_mcp_touchdesigner.operations import set_timeline_state

    class _AdvancingTimeline:
        seconds = 0.0

        def __init__(self):
            self._frame = 10.0
            self._play = True
            self.events = []

        @property
        def frame(self):
            return self._frame

        @frame.setter
        def frame(self, value):
            self.events.append(("frame", value, self._play))
            self._frame = value + 1 if self._play else value

        @property
        def play(self):
            return self._play

        @play.setter
        def play(self, value):
            self.events.append(("play", value))
            self._play = value

    timeline = _AdvancingTimeline()
    fake_td._operators["/"].time = timeline

    changed = set_timeline_state(frame=42.0, play=False, cook_rate=30.0, real_time=False)
    restored = set_timeline_state(frame=10.0, play=True, cook_rate=60.0, real_time=True)

    assert timeline.events[:2] == [("play", False), ("frame", 42.0, False)]
    assert changed["after"]["frame"] == 42.0
    assert changed["after"]["play"] is False
    assert restored["after"]["frame"] == 10.0
    assert restored["after"]["play"] is True


def test_timeline_readback_mismatch_rolls_back(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, set_timeline_state

    class _RejectingProject(_Project):
        def __init__(self):
            self._cook_rate = 60.0
            self.realTime = True

        @property
        def cookRate(self):
            return self._cook_rate

        @cookRate.setter
        def cookRate(self, value):
            if value != 30.0:
                self._cook_rate = value

    fake_td.project = _RejectingProject()

    with pytest.raises(TouchDesignerOperationError, match="rolled back"):
        set_timeline_state(frame=42.0, cook_rate=30.0)

    assert fake_td._operators["/"].time.frame == 1.0
    assert fake_td.project.cookRate == 60.0


def test_delete_requires_host_readback(fake_td):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, delete_operator

    operator = _Operator("stuck1", "/project1/stuck1", "nullTOP", "TOP")
    operator.destroy = lambda: None
    fake_td._operators[operator.path] = operator

    with pytest.raises(TouchDesignerOperationError, match="did not delete"):
        delete_operator(operator.path)


def test_direct_calls_do_not_coerce_schema_types(fake_td, tmp_path):
    from dcc_mcp_touchdesigner.operations import (
        TouchDesignerOperationError,
        capture_top,
        list_operators,
        save_project,
        set_timeline_state,
    )

    with pytest.raises(TouchDesignerOperationError, match="integer"):
        list_operators("/", limit="2")
    with pytest.raises(TouchDesignerOperationError, match="path"):
        list_operators(0)
    with pytest.raises(TouchDesignerOperationError, match="recurse"):
        list_operators("/", recurse="false")
    with pytest.raises(TouchDesignerOperationError, match="type_filter"):
        list_operators("/", type_filter=42)
    with pytest.raises(TouchDesignerOperationError, match="number"):
        set_timeline_state(frame="42")
    with pytest.raises(TouchDesignerOperationError, match="boolean"):
        save_project(str(tmp_path / "demo.toe"), overwrite="false")
    with pytest.raises(TouchDesignerOperationError, match="boolean"):
        capture_top("/project1/noise1", str(tmp_path / "preview.png"), overwrite=1)
    with pytest.raises(TouchDesignerOperationError, match="path must be a string"):
        save_project(tmp_path / "demo.toe")
    with pytest.raises(TouchDesignerOperationError, match="output_path must be a string"):
        capture_top("/project1/noise1", tmp_path / "preview.png")


def test_project_save_reports_verified_incremented_active_path(fake_td, tmp_path):
    from dcc_mcp_touchdesigner.operations import save_project

    class _IncrementingProject(_Project):
        def save(self, path: str) -> bool:
            requested = Path(path)
            active = requested.with_name(f"{requested.stem}.1{requested.suffix}")
            requested.write_bytes(b"touchdesigner-project-incremented")
            active.write_bytes(b"touchdesigner-project-incremented")
            self.name = active.name
            self.folder = str(active.parent)
            return True

    fake_td.project = _IncrementingProject()
    artifact = save_project(str(tmp_path / "showcase.toe"))

    assert artifact["path"] == str((tmp_path / "showcase.toe").resolve())
    assert artifact["active_project_path"] == str((tmp_path / "showcase.1.toe").resolve())
    assert artifact["incremented"] is True
    assert artifact["sha256"] == "edcda08cb77bde96ac48231cd76f3e7198f40898a999ef1c86df91fe77492cf4"


def test_capture_top_requires_a_real_top_family(fake_td, tmp_path):
    from dcc_mcp_touchdesigner.operations import TouchDesignerOperationError, capture_top

    save_capable_dat = _Top("not_a_top", "/project1/not_a_top", "textDAT", "DAT")
    fake_td._operators[save_capable_dat.path] = save_capable_dat

    with pytest.raises(TouchDesignerOperationError, match="not a TOP"):
        capture_top(save_capable_dat.path, str(tmp_path / "must-not-exist.png"))

    assert not (tmp_path / "must-not-exist.png").exists()
