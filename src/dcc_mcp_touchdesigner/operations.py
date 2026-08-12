"""Typed TouchDesigner operations executed exclusively on the host thread."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional


class TouchDesignerOperationError(RuntimeError):
    """Raised when a typed host operation cannot satisfy its contract."""


def _td() -> Any:
    import td

    return td


def _json_value(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth >= 3:
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_value(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item, depth=depth + 1) for key, item in value.items()}
    return str(value)


def _resolve_operator(path: str) -> Any:
    if not isinstance(path, str) or not path.strip():
        raise TouchDesignerOperationError("operator path must be a non-empty string")
    operator = _td().op(path.strip())
    if operator is None:
        raise TouchDesignerOperationError(f"operator not found: {path}")
    return operator


def operator_summary(operator: Any) -> dict[str, Any]:
    """Return a stable JSON summary without leaking opaque TD objects."""
    op_type = getattr(operator, "OPType", None)
    if op_type is None:
        op_type = getattr(operator, "type", type(operator).__name__)
    return {
        "name": str(getattr(operator, "name", "")),
        "path": str(getattr(operator, "path", operator)),
        "type": str(op_type),
        "family": str(getattr(operator, "family", "")),
    }


def get_project_info() -> dict[str, Any]:
    td = _td()
    project = td.project
    app = td.app
    root = td.op("/")
    return {
        "project_name": str(project.name),
        "project_folder": str(project.folder),
        "touchdesigner_version": str(app.version),
        "product": str(app.product),
        "process_id": int(app.processId),
        "cook_rate": float(project.cookRate),
        "root_operator_count": len(getattr(root, "children", ())) if root is not None else 0,
    }


def list_operators(
    path: str = "/",
    *,
    recurse: bool = False,
    type_filter: Optional[str] = None,
) -> dict[str, Any]:
    parent = _resolve_operator(path or "/")
    filter_norm = (type_filter or "").strip().lower()
    results: list[dict[str, Any]] = []

    def visit(operator: Any) -> None:
        for child in getattr(operator, "children", ()):
            summary = operator_summary(child)
            searchable = {summary["type"].lower(), summary["family"].lower()}
            if not filter_norm or filter_norm in searchable:
                results.append(summary)
            if recurse:
                visit(child)

    visit(parent)
    return {
        "path": str(getattr(parent, "path", path)),
        "count": len(results),
        "operators": results,
    }


def get_operator_parameters(path: str, names: Optional[list[str]] = None) -> dict[str, Any]:
    operator = _resolve_operator(path)
    requested = {name for name in names or [] if name}
    parameters: dict[str, Any] = {}
    for parameter in operator.pars():
        name = str(parameter.name)
        if requested and name not in requested:
            continue
        try:
            value = parameter.eval()
        except Exception:
            value = str(parameter)
        parameters[name] = {
            "value": _json_value(value),
            "label": str(getattr(parameter, "label", name)),
            "default": _json_value(getattr(parameter, "default", None)),
            "mode": str(getattr(parameter, "mode", "")),
        }
    missing = sorted(requested.difference(parameters))
    return {
        "operator": operator_summary(operator),
        "parameter_count": len(parameters),
        "parameters": parameters,
        "missing": missing,
    }


def set_operator_parameter(path: str, parameter: str, value: Any) -> dict[str, Any]:
    operator = _resolve_operator(path)
    if not isinstance(parameter, str) or not parameter.strip():
        raise TouchDesignerOperationError("parameter must be a non-empty string")
    parameter_ref = operator.par[parameter.strip()]
    if parameter_ref is None:
        raise TouchDesignerOperationError(f"parameter not found on {path}: {parameter}")
    parameter_ref.val = value
    return {
        "operator": operator_summary(operator),
        "parameter": parameter.strip(),
        "value": _json_value(parameter_ref.eval()),
    }


def create_operator(parent_path: str, operator_type: str, name: Optional[str] = None) -> dict[str, Any]:
    parent = _resolve_operator(parent_path)
    create = getattr(parent, "create", None)
    if not callable(create):
        raise TouchDesignerOperationError(f"operator cannot contain children: {parent_path}")
    if not isinstance(operator_type, str) or not operator_type.strip():
        raise TouchDesignerOperationError("operator_type must be a non-empty TouchDesigner type name")
    requested_name = name.strip() if isinstance(name, str) and name.strip() else None
    operator = create(operator_type.strip(), requested_name) if requested_name else create(operator_type.strip())
    return {"operator": operator_summary(operator), "parent_path": str(getattr(parent, "path", parent_path))}


def connect_operators(
    source_path: str,
    target_path: str,
    *,
    output_index: int = 0,
    input_index: int = 0,
) -> dict[str, Any]:
    source = _resolve_operator(source_path)
    target = _resolve_operator(target_path)
    if output_index < 0 or input_index < 0:
        raise TouchDesignerOperationError("connector indices must be non-negative")
    outputs = source.outputConnectors
    inputs = target.inputConnectors
    if output_index >= len(outputs):
        raise TouchDesignerOperationError(f"source connector index out of range: {output_index}")
    if input_index >= len(inputs):
        raise TouchDesignerOperationError(f"target connector index out of range: {input_index}")
    outputs[output_index].connect(inputs[input_index])
    return {
        "source": operator_summary(source),
        "target": operator_summary(target),
        "output_index": output_index,
        "input_index": input_index,
    }


def delete_operator(path: str) -> dict[str, Any]:
    operator = _resolve_operator(path)
    normalized_path = str(getattr(operator, "path", path))
    if normalized_path == "/":
        raise TouchDesignerOperationError("the TouchDesigner root operator cannot be deleted")
    summary = operator_summary(operator)
    operator.destroy()
    return {"deleted": summary}


def save_project(path: str, *, overwrite: bool = False) -> dict[str, Any]:
    output_path = Path(path).expanduser().resolve()
    if output_path.suffix.lower() != ".toe":
        raise TouchDesignerOperationError("project path must use the .toe extension")
    if output_path.exists() and not overwrite:
        raise TouchDesignerOperationError(f"project already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    saved = bool(_td().project.save(str(output_path)))
    if not saved or not output_path.is_file():
        raise TouchDesignerOperationError(f"TouchDesigner did not save the project: {output_path}")
    return {
        "path": str(output_path),
        "bytes": output_path.stat().st_size,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def capture_top(path: str, output_path: str, *, overwrite: bool = False) -> dict[str, Any]:
    operator = _resolve_operator(path)
    save = getattr(operator, "save", None)
    if not callable(save):
        raise TouchDesignerOperationError(f"operator does not support image export: {path}")
    target = Path(output_path).expanduser().resolve()
    if target.suffix.lower() != ".png":
        raise TouchDesignerOperationError("capture output_path must use the .png extension")
    if target.exists() and not overwrite:
        raise TouchDesignerOperationError(f"capture already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    save(str(target))
    if not target.is_file():
        raise TouchDesignerOperationError(f"TouchDesigner did not write the capture: {target}")
    return {
        "operator": operator_summary(operator),
        "path": str(target),
        "width": int(getattr(operator, "width", 0)),
        "height": int(getattr(operator, "height", 0)),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }


__all__ = [
    "TouchDesignerOperationError",
    "capture_top",
    "connect_operators",
    "create_operator",
    "delete_operator",
    "get_operator_parameters",
    "get_project_info",
    "list_operators",
    "operator_summary",
    "save_project",
    "set_operator_parameter",
]
