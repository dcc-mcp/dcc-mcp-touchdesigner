"""Release bundle integrity tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from zipfile import ZipFile


def _packaging_module():
    path = Path(__file__).parent.parent / "packaging" / "assemble_release.py"
    spec = importlib.util.spec_from_file_location("touchdesigner_assemble_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_zip_bootstraps_the_embedded_wheel(tmp_path):
    module = _packaging_module()
    wheel = tmp_path / "dcc_mcp_touchdesigner-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    archive = tmp_path / "release.zip"

    module.assemble_zip(archive, wheel)

    with ZipFile(archive) as bundle:
        assert bundle.namelist() == [
            "bootstrap.py",
            "payload/dcc_mcp_touchdesigner-0.1.0-py3-none-any.whl",
        ]
        bootstrap = bundle.read("bootstrap.py").decode("utf-8")
    assert "\"payload\", 'dcc_mcp_touchdesigner-0.1.0-py3-none-any.whl'" in bootstrap
    assert "sys.path.insert(0, _WHEEL)" in bootstrap
