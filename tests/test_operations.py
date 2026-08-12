"""Typed TouchDesigner operation contract tests with an in-memory host."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


class _Parameter:
    def __init__(self, name: str, value):
        self.name = name
        self.label = name.title()
        self.default = value
        self.mode = "CONSTANT"
        self.val = value

    def eval(self):
        return self.val


class _ParameterCollection:
    def __init__(self, parameters):
        self._parameters = {parameter.name: parameter for parameter in parameters}

    def __getitem__(self, name):
        return self._parameters.get(name)


class _Connector:
    def __init__(self):
        self.target = None

    def connect(self, target) -> None:
        self.target = target


class _Operator:
    def __init__(self, name: str, path: str, op_type: str = "baseCOMP", family: str = "COMP"):
        self.name = name
        self.path = path
        self.OPType = op_type
        self.family = family
        self.children: list[_Operator] = []
        self.par = _ParameterCollection([_Parameter("gain", 1.0)])
        self.outputConnectors = [_Connector()]
        self.inputConnectors = [_Connector()]
        self.destroyed = False

    def __str__(self) -> str:
        return self.path

    def pars(self):
        return list(self.par._parameters.values())

    def create(self, operator_type: str, name: str | None = None):
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


class _Project:
    name = "demo.toe"
    folder = "C:/projects/demo"
    cookRate = 60.0

    def save(self, path: str) -> bool:
        Path(path).write_bytes(b"touchdesigner-project")
        return True


class _Td:
    def __init__(self) -> None:
        root = _Operator("root", "/")
        project = _Operator("project1", "/project1")
        top = _Top("noise1", "/project1/noise1", "noiseTOP", "TOP")
        root.children.append(project)
        project.children.append(top)
        self._operators = {operator.path: operator for operator in (root, project, top)}
        self.project = _Project()
        self.app = SimpleNamespace(version="2025.33070", product="TouchDesigner", processId=4242)

    def op(self, path: str):
        return self._operators.get(path)


@pytest.fixture
def fake_td(monkeypatch):
    td = _Td()
    monkeypatch.setitem(sys.modules, "td", td)
    return td


def test_project_and_operator_inspection(fake_td):
    from dcc_mcp_touchdesigner.operations import get_operator_parameters, get_project_info, list_operators

    project = get_project_info()
    listing = list_operators("/", recurse=True, type_filter="TOP")
    parameters = get_operator_parameters("/project1/noise1", names=["gain", "missing"])

    assert project["project_name"] == "demo.toe"
    assert project["touchdesigner_version"] == "2025.33070"
    assert listing["count"] == 1
    assert listing["operators"][0]["path"] == "/project1/noise1"
    assert parameters["parameters"]["gain"]["value"] == 1.0
    assert parameters["missing"] == ["missing"]


def test_create_connect_update_and_delete(fake_td):
    from dcc_mcp_touchdesigner.operations import (
        connect_operators,
        create_operator,
        delete_operator,
        set_operator_parameter,
    )

    created = create_operator("/project1", "levelTOP", "grade1")
    grade = fake_td._operators["/project1"].children[-1]
    fake_td._operators[grade.path] = grade
    connected = connect_operators("/project1/noise1", grade.path)
    updated = set_operator_parameter(grade.path, "gain", 2.5)
    deleted = delete_operator(grade.path)

    assert created["operator"]["path"] == "/project1/grade1"
    assert fake_td._operators["/project1/noise1"].outputConnectors[0].target is grade.inputConnectors[0]
    assert connected["input_index"] == 0
    assert updated["value"] == 2.5
    assert deleted["deleted"]["path"] == grade.path
    assert grade.destroyed


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
