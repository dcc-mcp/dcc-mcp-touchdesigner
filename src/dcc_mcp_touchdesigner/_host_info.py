"""Bounded helpers for TouchDesigner host identity."""

from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def touchdesigner_release(app: Any) -> str:
    """Return the public TouchDesigner release identifier.

    TouchDesigner still reports the legacy generation (for example ``099``)
    through ``app.version``.  Current hosts expose the public ``year.build``
    identifier through ``app.build``; older hosts may expose only the numeric
    build component, which is combined with the generation.
    """
    version = _text(getattr(app, "version", ""))
    build = _text(getattr(app, "build", ""))
    if build:
        if "." in build or not version:
            return build
        return f"{version}.{build}"
    return version or "unknown"
