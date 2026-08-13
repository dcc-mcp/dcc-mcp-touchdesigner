"""Typed TouchDesigner operations executed exclusively on the host thread."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Optional

from dcc_mcp_touchdesigner._host_info import touchdesigner_release

MAX_OPERATOR_RESULTS = 5_000
DEFAULT_OPERATOR_RESULTS = 500
MAX_PARAMETER_NAMES = 256
MAX_PARAMETER_RESULTS = 2_000
DEFAULT_PARAMETER_RESULTS = 500
MAX_JSON_VALUE_BYTES = 64 * 1024
MAX_DAT_BYTES = 1 * 1024 * 1024
MAX_TEXT_CHARS = 4_096
_MUTABLE_DAT_TYPES = frozenset({"textdat", "tabledat"})
_MUTABLE_FLAGS = frozenset({"bypass", "display", "lock", "render", "viewer"})
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MISSING = object()


class TouchDesignerOperationError(RuntimeError):
    """Raised when a typed host operation cannot satisfy its contract."""


def _td() -> Any:
    import td

    return td


def _json_value(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if depth >= 3:
        return _bounded_text(value)
    if isinstance(value, (list, tuple)):
        return [_json_value(item, depth=depth + 1) for item in value[:256]]
    if isinstance(value, dict):
        return {
            _bounded_text(key, max_chars=256): _json_value(item, depth=depth + 1)
            for key, item in list(value.items())[:256]
        }
    return _bounded_text(value)


def _bounded_text(value: Any, *, max_chars: int = MAX_TEXT_CHARS) -> str:
    text = str(value)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1]}…"


def _bounded_int(value: Any, *, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise TouchDesignerOperationError(f"{field} must be an integer")
    result = value
    if result < minimum or result > maximum:
        raise TouchDesignerOperationError(f"{field} must be between {minimum} and {maximum}")
    return result


def _bounded_number(value: Any, *, field: str, minimum: float, maximum: float) -> float:
    if type(value) not in (int, float):
        raise TouchDesignerOperationError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise TouchDesignerOperationError(f"{field} must be between {minimum} and {maximum}")
    return result


def _require_name(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TouchDesignerOperationError(f"{field} must be one bounded TouchDesigner name")
    name = value.strip()
    if not name or len(name) > 256 or any(character in name for character in ("/", "\\", ":", "\x00")):
        raise TouchDesignerOperationError(f"{field} must be one bounded TouchDesigner name")
    return name


def _require_json_value(value: Any) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TouchDesignerOperationError("value must be bounded JSON data") from exc
    if len(encoded) > MAX_JSON_VALUE_BYTES:
        raise TouchDesignerOperationError("value exceeds the 64 KiB JSON limit")
    return value


def _parameter_state(parameter: Any) -> dict[str, Any]:
    return {attribute: getattr(parameter, attribute, _MISSING) for attribute in ("val", "expr", "bindExpr", "mode")}


def _restore_parameter_state(parameter: Any, state: dict[str, Any]) -> None:
    # Par.val intentionally switches TouchDesigner parameters to constant mode.
    # Restore expression/bind payloads before restoring the original mode last.
    for attribute in ("val", "expr", "bindExpr", "mode"):
        value = state[attribute]
        if value is not _MISSING:
            setattr(parameter, attribute, value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_operator(path: str) -> Any:
    if not isinstance(path, str):
        raise TouchDesignerOperationError("operator path must be an absolute TouchDesigner path")
    exact_path = path.strip()
    path_parts = exact_path.split("/")[1:]
    if (
        not exact_path.startswith("/")
        or len(exact_path) > 1_024
        or "\x00" in exact_path
        or (exact_path != "/" and any(part in {"", ".", ".."} for part in path_parts))
    ):
        raise TouchDesignerOperationError("operator path must be an absolute TouchDesigner path")
    operator = _td().op(exact_path)
    if operator is None:
        raise TouchDesignerOperationError(f"operator not found: {path}")
    return operator


def operator_summary(operator: Any) -> dict[str, Any]:
    """Return a stable JSON summary without leaking opaque TD objects."""
    op_type = getattr(operator, "OPType", None)
    if op_type is None:
        op_type = getattr(operator, "type", type(operator).__name__)
    return {
        "name": _bounded_text(getattr(operator, "name", ""), max_chars=256),
        "path": _bounded_text(getattr(operator, "path", operator), max_chars=1_024),
        "type": _bounded_text(op_type, max_chars=256),
        "family": _bounded_text(getattr(operator, "family", ""), max_chars=64),
    }


def get_project_info() -> dict[str, Any]:
    td = _td()
    project = td.project
    app = td.app
    root = td.op("/")
    return {
        "project_name": _bounded_text(project.name, max_chars=256),
        "touchdesigner_version": _bounded_text(touchdesigner_release(app), max_chars=128),
        "touchdesigner_generation": _bounded_text(getattr(app, "version", ""), max_chars=128),
        "touchdesigner_build": _bounded_text(getattr(app, "build", ""), max_chars=128),
        "product": _bounded_text(app.product, max_chars=128),
        "process_id": int(app.processId),
        "cook_rate": float(project.cookRate),
        "real_time": bool(getattr(project, "realTime", True)),
        "root_operator_count": len(getattr(root, "children", ())) if root is not None else 0,
    }


def list_operators(
    path: str = "/",
    *,
    recurse: bool = False,
    type_filter: Optional[str] = None,
    limit: int = DEFAULT_OPERATOR_RESULTS,
) -> dict[str, Any]:
    if not isinstance(path, str):
        raise TouchDesignerOperationError("path must be a string")
    if type(recurse) is not bool:
        raise TouchDesignerOperationError("recurse must be a boolean")
    parent = _resolve_operator(path or "/")
    bounded_limit = _bounded_int(limit, field="limit", minimum=1, maximum=MAX_OPERATOR_RESULTS)
    if type_filter is not None and not isinstance(type_filter, str):
        raise TouchDesignerOperationError("type_filter must be a string")
    exact_filter = (type_filter or "").strip()
    if len(exact_filter) > 256:
        raise TouchDesignerOperationError("type_filter must contain at most 256 characters")
    filter_norm = exact_filter.casefold()
    results: list[dict[str, Any]] = []
    matched = 0
    truncated = False

    def visit(operator: Any) -> None:
        nonlocal matched, truncated
        if truncated:
            return
        for child in getattr(operator, "children", ()):
            summary = operator_summary(child)
            searchable = {summary["type"].casefold(), summary["family"].casefold()}
            if not filter_norm or filter_norm in searchable:
                matched += 1
                if matched <= bounded_limit:
                    results.append(summary)
                else:
                    truncated = True
                    return
            if recurse:
                visit(child)
                if truncated:
                    return

    visit(parent)
    return {
        "path": str(getattr(parent, "path", path)),
        "count": len(results),
        "operators": results,
        "limit": bounded_limit,
        "truncated": truncated,
    }


def get_operator_parameters(
    path: str,
    names: Optional[list[str]] = None,
    *,
    limit: int = DEFAULT_PARAMETER_RESULTS,
) -> dict[str, Any]:
    operator = _resolve_operator(path)
    bounded_limit = _bounded_int(limit, field="limit", minimum=1, maximum=MAX_PARAMETER_RESULTS)
    if names is not None and (not isinstance(names, list) or len(names) > MAX_PARAMETER_NAMES):
        raise TouchDesignerOperationError(f"names must contain at most {MAX_PARAMETER_NAMES} parameter names")
    requested = {_require_name(name, "parameter") for name in names or []}
    parameters: dict[str, Any] = {}
    truncated = False
    for parameter in operator.pars():
        name = _bounded_text(parameter.name, max_chars=256)
        if requested and name not in requested:
            continue
        if not requested and len(parameters) >= bounded_limit:
            truncated = True
            break
        try:
            value = parameter.eval()
        except Exception:
            value = _bounded_text(parameter)
        parameters[name] = {
            "value": _json_value(value),
            "label": _bounded_text(getattr(parameter, "label", name), max_chars=256),
            "default": _json_value(getattr(parameter, "default", None)),
            "mode": _bounded_text(getattr(parameter, "mode", ""), max_chars=64),
        }
    missing = sorted(requested.difference(parameters))
    return {
        "operator": operator_summary(operator),
        "parameter_count": len(parameters),
        "parameters": parameters,
        "missing": missing,
        "limit": bounded_limit,
        "truncated": truncated,
    }


def inspect_operator(path: str) -> dict[str, Any]:
    """Return bounded state, flags, connections, and cook diagnostics."""
    operator = _resolve_operator(path)
    flags = {flag: bool(getattr(operator, flag)) for flag in sorted(_MUTABLE_FLAGS) if hasattr(operator, flag)}
    return {
        "operator": operator_summary(operator),
        "flags": flags,
        "input_count": len(getattr(operator, "inputConnectors", ())),
        "output_count": len(getattr(operator, "outputConnectors", ())),
        "cook": {
            "frame": float(getattr(operator, "cookFrame", 0.0)),
            "time_ms": float(getattr(operator, "cookTime", 0.0)),
        },
    }


def _connection_summary(connector: Any) -> dict[str, Any]:
    owner = getattr(connector, "owner", None)
    return operator_summary(owner) if owner is not None else {"name": "", "path": "", "type": "", "family": ""}


def _connector_identity(connector: Any) -> tuple[str, int, Optional[bool], Optional[bool]]:
    owner = getattr(connector, "owner", None)
    owner_path = str(getattr(owner, "path", owner)) if owner is not None else ""
    return (
        owner_path,
        int(getattr(connector, "index", -1)),
        getattr(connector, "isInput", None),
        getattr(connector, "isOutput", None),
    )


def _same_connector(left: Any, right: Any) -> bool:
    return left is right or _connector_identity(left) == _connector_identity(right)


def _same_connector_set(left: list[Any], right: list[Any]) -> bool:
    return len(left) == len(right) and all(any(_same_connector(item, expected) for item in left) for expected in right)


def _restore_input_connections(input_connector: Any, previous: list[Any]) -> None:
    disconnect = getattr(input_connector, "disconnect", None)
    if not callable(disconnect):
        raise TouchDesignerOperationError("input connector cannot be restored")
    disconnect()
    for output_connector in previous:
        connect = getattr(output_connector, "connect", None)
        if not callable(connect):
            raise TouchDesignerOperationError("previous output connector cannot be restored")
        connect(input_connector)
    restored = list(getattr(input_connector, "connections", ()))
    if not _same_connector_set(restored, previous):
        raise TouchDesignerOperationError("TouchDesigner did not verify the restored input connections")


def inspect_connections(path: str) -> dict[str, Any]:
    """Return bounded connector topology for one operator."""
    operator = _resolve_operator(path)

    def summarize(connectors: Any) -> list[dict[str, Any]]:
        connector_list = list(connectors)
        if len(connector_list) > 256:
            raise TouchDesignerOperationError("operator has more than 256 connectors")
        summaries: list[dict[str, Any]] = []
        for fallback_index, connector in enumerate(connector_list):
            connected = list(getattr(connector, "connections", ()))
            if len(connected) > 256:
                raise TouchDesignerOperationError("connector has more than 256 connections")
            summaries.append(
                {
                    "index": int(getattr(connector, "index", fallback_index)),
                    "description": _bounded_text(getattr(connector, "description", ""), max_chars=256),
                    "connections": [_connection_summary(item) for item in connected],
                }
            )
        return summaries

    return {
        "operator": operator_summary(operator),
        "inputs": summarize(getattr(operator, "inputConnectors", ())),
        "outputs": summarize(getattr(operator, "outputConnectors", ())),
    }


def set_operator_parameter(path: str, parameter: str, value: Any) -> dict[str, Any]:
    operator = _resolve_operator(path)
    exact_parameter = _require_name(parameter, "parameter")
    exact_value = _require_json_value(value)
    parameter_ref = operator.par[exact_parameter]
    if parameter_ref is None:
        raise TouchDesignerOperationError(f"parameter not found on {path}: {parameter}")
    previous = _parameter_state(parameter_ref)
    try:
        parameter_ref.val = exact_value
        evaluated = _json_value(parameter_ref.eval())
    except Exception as exc:
        try:
            _restore_parameter_state(parameter_ref, previous)
        except Exception as rollback_exc:
            raise TouchDesignerOperationError(
                "parameter update failed and its previous state could not be restored"
            ) from rollback_exc
        raise TouchDesignerOperationError("parameter update failed and was rolled back") from exc
    return {
        "operator": operator_summary(operator),
        "parameter": exact_parameter,
        "value": evaluated,
    }


def pulse_operator_parameter(
    path: str,
    parameter: str,
    *,
    value: Any = 1,
    frames: int = 0,
    seconds: float = 0.0,
) -> dict[str, Any]:
    """Pulse one explicit parameter through TouchDesigner's Par contract."""
    operator = _resolve_operator(path)
    exact_parameter = _require_name(parameter, "parameter")
    exact_value = _require_json_value(value)
    exact_frames = _bounded_int(frames, field="frames", minimum=0, maximum=1_000_000)
    exact_seconds = _bounded_number(seconds, field="seconds", minimum=0.0, maximum=86_400.0)
    if exact_frames and exact_seconds:
        raise TouchDesignerOperationError("frames and seconds cannot both be non-zero")
    parameter_ref = operator.par[exact_parameter]
    if parameter_ref is None:
        raise TouchDesignerOperationError(f"parameter not found on {path}: {parameter}")
    pulse = getattr(parameter_ref, "pulse", None)
    if not callable(pulse):
        raise TouchDesignerOperationError(f"parameter cannot be pulsed on {path}: {parameter}")
    pulse(exact_value, frames=exact_frames, seconds=exact_seconds)
    return {
        "operator": operator_summary(operator),
        "parameter": exact_parameter,
        "value": _json_value(exact_value),
        "frames": exact_frames,
        "seconds": exact_seconds,
        "accepted": True,
    }


def set_operator_flags(path: str, flags: dict[str, bool]) -> dict[str, Any]:
    """Atomically update allowlisted operator flags with rollback on failure."""
    operator = _resolve_operator(path)
    if not isinstance(flags, dict) or not flags:
        raise TouchDesignerOperationError("flags must contain at least one allowlisted flag")
    if len(flags) > len(_MUTABLE_FLAGS) or any(flag not in _MUTABLE_FLAGS for flag in flags):
        raise TouchDesignerOperationError(f"flags may contain only: {', '.join(sorted(_MUTABLE_FLAGS))}")
    if any(type(value) is not bool for value in flags.values()):
        raise TouchDesignerOperationError("operator flag values must be booleans")
    unavailable = sorted(flag for flag in flags if not hasattr(operator, flag))
    if unavailable:
        raise TouchDesignerOperationError(f"operator does not expose flags: {', '.join(unavailable)}")
    before = {flag: bool(getattr(operator, flag)) for flag in flags}
    try:
        for flag, value in flags.items():
            setattr(operator, flag, value)
    except Exception as exc:
        for flag, value in before.items():
            try:
                setattr(operator, flag, value)
            except Exception:
                pass
        raise TouchDesignerOperationError("operator flag update failed and was rolled back") from exc
    after = {flag: bool(getattr(operator, flag)) for flag in flags}
    if after != flags:
        for flag, value in before.items():
            try:
                setattr(operator, flag, value)
            except Exception:
                pass
        raise TouchDesignerOperationError("TouchDesigner did not verify the requested operator flags")
    return {"operator": operator_summary(operator), "before": before, "after": after}


def set_operator_layout(
    path: str,
    *,
    x: Optional[int] = None,
    y: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> dict[str, Any]:
    """Atomically update bounded Network Editor layout fields for one operator."""
    operator = _resolve_operator(path)
    if all(value is None for value in (x, y, width, height)):
        raise TouchDesignerOperationError("at least one operator layout field must be supplied")
    requested: list[tuple[str, str, int]] = []
    if x is not None:
        requested.append(("x", "nodeX", _bounded_int(x, field="x", minimum=-1_000_000, maximum=1_000_000)))
    if y is not None:
        requested.append(("y", "nodeY", _bounded_int(y, field="y", minimum=-1_000_000, maximum=1_000_000)))
    if width is not None:
        requested.append(("width", "nodeWidth", _bounded_int(width, field="width", minimum=10, maximum=10_000)))
    if height is not None:
        requested.append(("height", "nodeHeight", _bounded_int(height, field="height", minimum=10, maximum=10_000)))
    unavailable = [public_name for public_name, attribute, _value in requested if not hasattr(operator, attribute)]
    if unavailable:
        raise TouchDesignerOperationError(f"operator does not expose layout fields: {', '.join(unavailable)}")
    before = {public_name: int(getattr(operator, attribute)) for public_name, attribute, _value in requested}
    try:
        for _public_name, attribute, value in requested:
            setattr(operator, attribute, value)
        after = {public_name: int(getattr(operator, attribute)) for public_name, attribute, _value in requested}
        expected = {public_name: value for public_name, _attribute, value in requested}
        if after != expected:
            raise TouchDesignerOperationError("TouchDesigner did not verify the requested operator layout")
    except Exception as exc:
        for public_name, attribute, _value in reversed(requested):
            try:
                setattr(operator, attribute, before[public_name])
            except Exception:
                pass
        restored = {public_name: int(getattr(operator, attribute)) for public_name, attribute, _value in requested}
        if restored != before:
            raise TouchDesignerOperationError(
                "operator layout update failed and its previous state could not be restored"
            ) from exc
        raise TouchDesignerOperationError("operator layout update failed and was rolled back") from exc
    return {"operator": operator_summary(operator), "before": before, "after": after}


def create_operator(parent_path: str, operator_type: str, name: Optional[str] = None) -> dict[str, Any]:
    parent = _resolve_operator(parent_path)
    create = getattr(parent, "create", None)
    if not callable(create):
        raise TouchDesignerOperationError(f"operator cannot contain children: {parent_path}")
    exact_type = _require_name(operator_type, "operator_type")
    requested_name = _require_name(name, "name") if name is not None else None
    if requested_name and any(
        str(getattr(child, "name", "")) == requested_name for child in getattr(parent, "children", ())
    ):
        raise TouchDesignerOperationError(f"operator already exists below {parent_path}: {requested_name}")
    try:
        operator = create(exact_type, requested_name) if requested_name else create(exact_type)
    except Exception as exc:
        raise TouchDesignerOperationError(f"TouchDesigner could not create operator type: {exact_type}") from exc
    if operator is None or not any(child is operator for child in getattr(parent, "children", ())):
        destroy = getattr(operator, "destroy", None)
        try:
            if callable(destroy):
                destroy()
        except Exception as cleanup_exc:
            raise TouchDesignerOperationError(
                "TouchDesigner did not register the created operator and cleanup failed"
            ) from cleanup_exc
        raise TouchDesignerOperationError("TouchDesigner did not register the created operator below its parent")
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
    exact_output_index = _bounded_int(output_index, field="output_index", minimum=0, maximum=255)
    exact_input_index = _bounded_int(input_index, field="input_index", minimum=0, maximum=255)
    outputs = source.outputConnectors
    inputs = target.inputConnectors
    if exact_output_index >= len(outputs):
        raise TouchDesignerOperationError(f"source connector index out of range: {exact_output_index}")
    if exact_input_index >= len(inputs):
        raise TouchDesignerOperationError(f"target connector index out of range: {exact_input_index}")
    output_connector = outputs[exact_output_index]
    input_connector = inputs[exact_input_index]
    previous_connections = list(getattr(input_connector, "connections", ()))
    try:
        output_connector.connect(input_connector)
        verified = any(
            _same_connector(connector, output_connector)
            for connector in list(getattr(input_connector, "connections", ()))
        )
        if not verified:
            raise TouchDesignerOperationError("TouchDesigner did not verify the requested connection")
    except Exception as exc:
        try:
            _restore_input_connections(input_connector, previous_connections)
        except Exception as rollback_exc:
            raise TouchDesignerOperationError(
                "connection failed and its previous input could not be restored"
            ) from rollback_exc
        raise TouchDesignerOperationError("connection failed and its previous input was rolled back") from exc
    return {
        "source": operator_summary(source),
        "target": operator_summary(target),
        "output_index": exact_output_index,
        "input_index": exact_input_index,
        "verified_connected": True,
    }


def disconnect_operator_input(path: str, *, input_index: int = 0) -> dict[str, Any]:
    """Disconnect one exact input connector without touching sibling inputs or outputs."""
    operator = _resolve_operator(path)
    exact_index = _bounded_int(input_index, field="input_index", minimum=0, maximum=255)
    inputs = getattr(operator, "inputConnectors", ())
    if exact_index >= len(inputs):
        raise TouchDesignerOperationError(f"input connector index out of range: {exact_index}")
    connector = inputs[exact_index]
    raw_connections = list(getattr(connector, "connections", ()))
    if len(raw_connections) > 256:
        raise TouchDesignerOperationError("input connector has more than 256 connections")
    before_connections = [_connection_summary(item) for item in raw_connections]
    disconnect = getattr(connector, "disconnect", None)
    if not callable(disconnect):
        raise TouchDesignerOperationError(f"input connector cannot be disconnected: {exact_index}")
    try:
        disconnect()
        verified = not list(getattr(connector, "connections", ()))
        if not verified:
            raise TouchDesignerOperationError("TouchDesigner did not verify the requested disconnection")
    except Exception as exc:
        try:
            _restore_input_connections(connector, raw_connections)
        except Exception as rollback_exc:
            raise TouchDesignerOperationError(
                "disconnection failed and its previous input could not be restored"
            ) from rollback_exc
        raise TouchDesignerOperationError("disconnection failed and its previous input was rolled back") from exc
    return {
        "operator": operator_summary(operator),
        "input_index": exact_index,
        "previous_connections": before_connections,
        "verified_disconnected": verified,
    }


def get_dat_content(path: str, *, max_bytes: int = MAX_DAT_BYTES) -> dict[str, Any]:
    """Read one DAT through a bounded Unicode text contract."""
    operator = _resolve_operator(path)
    byte_limit = _bounded_int(max_bytes, field="max_bytes", minimum=1, maximum=MAX_DAT_BYTES)
    is_text = bool(getattr(operator, "isText", False))
    is_table = bool(getattr(operator, "isTable", False))
    if not is_text and not is_table:
        raise TouchDesignerOperationError(f"operator is not a DAT with text content: {path}")
    content = getattr(operator, "text", None)
    if not isinstance(content, str):
        raise TouchDesignerOperationError(f"DAT returned non-text content: {path}")
    encoded = content.encode("utf-8")
    if len(encoded) > byte_limit:
        raise TouchDesignerOperationError(f"DAT content exceeds max_bytes ({len(encoded)} > {byte_limit})")
    return {
        "operator": operator_summary(operator),
        "kind": "table" if is_table else "text",
        "content": content,
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "rows": int(getattr(operator, "numRows", 0)),
        "columns": int(getattr(operator, "numCols", 0)),
    }


def set_dat_content(path: str, content: str, *, expected_sha256: Optional[str] = None) -> dict[str, Any]:
    """Replace a Text/Table DAT with bounded optimistic-concurrency verification."""
    operator = _resolve_operator(path)
    op_type = str(getattr(operator, "OPType", getattr(operator, "type", ""))).casefold()
    if op_type not in _MUTABLE_DAT_TYPES:
        raise TouchDesignerOperationError("only a Text DAT or Table DAT can be edited through this tool")
    if getattr(operator, "isEditable", False) is not True:
        raise TouchDesignerOperationError(f"DAT is not editable: {path}")
    if not isinstance(content, str):
        raise TouchDesignerOperationError("content must be a Unicode string")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_DAT_BYTES:
        raise TouchDesignerOperationError(f"content exceeds the {MAX_DAT_BYTES}-byte limit")
    before = get_dat_content(path)
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str):
            raise TouchDesignerOperationError("expected_sha256 must be one SHA-256 hex digest")
        exact_hash = expected_sha256.strip().lower()
        if not _SHA256_RE.fullmatch(exact_hash):
            raise TouchDesignerOperationError("expected_sha256 must be one SHA-256 hex digest")
        if exact_hash != before["sha256"]:
            raise TouchDesignerOperationError("DAT content changed since the expected SHA-256 was observed")
    try:
        operator.text = content
        after = get_dat_content(path)
        if after["content"] != content:
            raise TouchDesignerOperationError("DAT did not preserve the requested Unicode content")
    except Exception as exc:
        try:
            operator.text = before["content"]
            restored = get_dat_content(path)
            if restored["sha256"] != before["sha256"]:
                raise TouchDesignerOperationError("DAT rollback readback did not match the previous content")
        except Exception as rollback_exc:
            raise TouchDesignerOperationError(
                "DAT content update failed and the previous content could not be restored"
            ) from rollback_exc
        raise TouchDesignerOperationError("DAT content update failed and the previous content was restored") from exc
    return {
        "operator": after["operator"],
        "before_sha256": before["sha256"],
        "after_sha256": after["sha256"],
        "bytes": after["bytes"],
    }


def get_timeline_state() -> dict[str, Any]:
    """Return root component time plus project cooking controls."""
    td = _td()
    root = td.op("/")
    timeline = getattr(root, "time", None) if root is not None else None
    if timeline is None:
        raise TouchDesignerOperationError("root TouchDesigner timeline is unavailable")
    project = td.project
    return {
        "frame": float(getattr(timeline, "frame")),
        "seconds": float(getattr(timeline, "seconds", 0.0)),
        "play": bool(getattr(timeline, "play")),
        "cook_rate": float(getattr(project, "cookRate")),
        "real_time": bool(getattr(project, "realTime")),
    }


def _timeline_value_matches(actual: Any, expected: Any) -> bool:
    if type(expected) is bool:
        return actual is expected
    return math.isclose(float(actual), float(expected), abs_tol=1e-9)


def set_timeline_state(
    *,
    frame: Optional[float] = None,
    play: Optional[bool] = None,
    cook_rate: Optional[float] = None,
    real_time: Optional[bool] = None,
) -> dict[str, Any]:
    """Atomically update explicitly supplied root timeline fields."""
    if all(value is None for value in (frame, play, cook_rate, real_time)):
        raise TouchDesignerOperationError("at least one timeline field must be supplied")
    if play is not None and type(play) is not bool:
        raise TouchDesignerOperationError("play must be a boolean")
    if real_time is not None and type(real_time) is not bool:
        raise TouchDesignerOperationError("real_time must be a boolean")
    exact_frame = (
        _bounded_number(frame, field="frame", minimum=0.0, maximum=1_000_000_000.0) if frame is not None else None
    )
    exact_rate = (
        _bounded_number(cook_rate, field="cook_rate", minimum=1.0, maximum=1_000.0) if cook_rate is not None else None
    )
    td = _td()
    root = td.op("/")
    timeline = getattr(root, "time", None) if root is not None else None
    if timeline is None:
        raise TouchDesignerOperationError("root TouchDesigner timeline is unavailable")
    project = td.project
    before = get_timeline_state()
    non_play_updates: list[tuple[Any, str, Any, Any, str]] = []
    if exact_frame is not None:
        non_play_updates.append((timeline, "frame", exact_frame, before["frame"], "frame"))
    if exact_rate is not None:
        non_play_updates.append((project, "cookRate", exact_rate, before["cook_rate"], "cook_rate"))
    if real_time is not None:
        non_play_updates.append((project, "realTime", real_time, before["real_time"], "real_time"))
    target_play = play if play is not None else before["play"]
    try:
        if before["play"] and non_play_updates:
            timeline.play = False
            if get_timeline_state()["play"] is not False:
                raise TouchDesignerOperationError("TouchDesigner did not pause the timeline for an atomic update")
        for owner, attribute, value, _previous, _result_key in non_play_updates:
            setattr(owner, attribute, value)
        staged = get_timeline_state()
        for _owner, _attribute, value, _previous, result_key in non_play_updates:
            if not _timeline_value_matches(staged[result_key], value):
                raise TouchDesignerOperationError(f"TouchDesigner did not verify timeline field: {result_key}")
        if play is not None or (before["play"] and non_play_updates):
            timeline.play = target_play
        after = get_timeline_state()
        if after["play"] is not target_play:
            raise TouchDesignerOperationError("TouchDesigner did not verify timeline field: play")
    except Exception as exc:
        try:
            timeline.play = False
        except Exception:
            pass
        for owner, attribute, _value, previous, _result_key in reversed(non_play_updates):
            try:
                setattr(owner, attribute, previous)
            except Exception:
                pass
        restored_staged = get_timeline_state()
        rollback_ok = all(
            _timeline_value_matches(restored_staged[result_key], previous)
            for _owner, _attribute, _value, previous, result_key in non_play_updates
        )
        try:
            timeline.play = before["play"]
        except Exception:
            rollback_ok = False
        restored = get_timeline_state()
        rollback_ok = rollback_ok and restored["play"] is before["play"]
        if not rollback_ok:
            raise TouchDesignerOperationError(
                "timeline update failed and its previous state could not be restored"
            ) from exc
        raise TouchDesignerOperationError("timeline update failed and was rolled back") from exc
    return {"before": before, "after": after}


def delete_operator(path: str) -> dict[str, Any]:
    operator = _resolve_operator(path)
    normalized_path = str(getattr(operator, "path", path))
    if normalized_path == "/":
        raise TouchDesignerOperationError("the TouchDesigner root operator cannot be deleted")
    summary = operator_summary(operator)
    operator.destroy()
    if _td().op(normalized_path) is not None:
        raise TouchDesignerOperationError(f"TouchDesigner did not delete operator: {normalized_path}")
    return {"deleted": summary, "verified_deleted": True}


def save_project(path: str, *, overwrite: bool = False) -> dict[str, Any]:
    if type(overwrite) is not bool:
        raise TouchDesignerOperationError("overwrite must be a boolean")
    if not isinstance(path, str):
        raise TouchDesignerOperationError("project path must be a string")
    requested_path = Path(path).expanduser()
    if not requested_path.is_absolute():
        raise TouchDesignerOperationError("project path must be absolute")
    output_path = requested_path.resolve()
    if output_path.suffix.lower() != ".toe":
        raise TouchDesignerOperationError("project path must use the .toe extension")
    if output_path.exists() and not overwrite:
        raise TouchDesignerOperationError(f"project already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    project = _td().project
    saved = bool(project.save(str(output_path)))
    if not saved or not output_path.is_file():
        raise TouchDesignerOperationError(f"TouchDesigner did not save the project: {output_path}")
    output_hash = _sha256_file(output_path)
    active_path = output_path
    active_name = str(getattr(project, "name", "")).strip()
    active_folder = str(getattr(project, "folder", "")).strip()
    if active_name and active_folder:
        candidate = (Path(active_folder).expanduser() / active_name).resolve()
        if candidate.is_file():
            active_path = candidate
            if _sha256_file(active_path) != output_hash:
                raise TouchDesignerOperationError(
                    "TouchDesigner saved an incremented project that does not match the requested path"
                )
    return {
        "path": str(output_path),
        "active_project_path": str(active_path),
        "incremented": active_path != output_path,
        "bytes": output_path.stat().st_size,
        "sha256": output_hash,
    }


def capture_top(path: str, output_path: str, *, overwrite: bool = False) -> dict[str, Any]:
    if type(overwrite) is not bool:
        raise TouchDesignerOperationError("overwrite must be a boolean")
    if not isinstance(output_path, str):
        raise TouchDesignerOperationError("capture output_path must be a string")
    operator = _resolve_operator(path)
    if getattr(operator, "isTOP", None) is not True and str(getattr(operator, "family", "")).casefold() != "top":
        raise TouchDesignerOperationError(f"operator is not a TOP: {path}")
    save = getattr(operator, "save", None)
    if not callable(save):
        raise TouchDesignerOperationError(f"operator does not support image export: {path}")
    requested_target = Path(output_path).expanduser()
    if not requested_target.is_absolute():
        raise TouchDesignerOperationError("capture output_path must be absolute")
    target = requested_target.resolve()
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
        "sha256": _sha256_file(target),
    }


__all__ = [
    "TouchDesignerOperationError",
    "capture_top",
    "connect_operators",
    "create_operator",
    "delete_operator",
    "disconnect_operator_input",
    "get_dat_content",
    "get_operator_parameters",
    "get_project_info",
    "get_timeline_state",
    "inspect_connections",
    "inspect_operator",
    "list_operators",
    "operator_summary",
    "pulse_operator_parameter",
    "save_project",
    "set_dat_content",
    "set_operator_flags",
    "set_operator_layout",
    "set_operator_parameter",
    "set_timeline_state",
]
