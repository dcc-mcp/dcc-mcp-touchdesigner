"""TouchDesigner DCC capabilities declaration."""

from __future__ import annotations

from dcc_mcp_core import DccCapabilities

_TOUCHDESIGNER_CAPS = DccCapabilities(
    scene_manager=True,
    transform=True,
    hierarchy=True,
    render_capture=True,
    selection=True,
    snapshot=True,
    undo_redo=False,
    file_operations=True,
    has_embedded_python=True,
    progress_reporting=False,
    scene_info=True,
    extensions={
        "node_graph": True,
        "real_time_rendering": True,
        "operator_family": True,
        "chop_channels": True,
        "touch_osc": True,
        "toe_file_format": True,
        "typed_dat_content": True,
        "typed_timeline": True,
        "typed_operator_layout": True,
        "arbitrary_python_tool": False,
        "component_system": True,
    },
)


def touchdesigner_capabilities() -> DccCapabilities:
    """Return the capabilities descriptor for TouchDesigner.

    Returns:
        DccCapabilities instance describing all supported TouchDesigner features.
    """
    return _TOUCHDESIGNER_CAPS


def touchdesigner_capabilities_dict() -> dict:
    """Return the TouchDesigner capabilities as a plain Python dict.

    Returns:
        dict with capability fields suitable for JSON serialisation.
    """
    caps = _TOUCHDESIGNER_CAPS
    return {
        "scene_manager": caps.scene_manager,
        "transform": caps.transform,
        "hierarchy": caps.hierarchy,
        "render_capture": caps.render_capture,
        "selection": caps.selection,
        "snapshot": caps.snapshot,
        "undo_redo": caps.undo_redo,
        "file_operations": caps.file_operations,
        "has_embedded_python": caps.has_embedded_python,
        "progress_reporting": caps.progress_reporting,
        "scene_info": caps.scene_info,
        "extensions": caps.extensions,
    }
