"""Dependency pins that a rerun of the published results relies on."""

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def _extra(name: str) -> list[Requirement]:
    project = tomllib.loads(PYPROJECT.read_text())["project"]
    return [Requirement(spec) for spec in project["optional-dependencies"][name]]


def test_lfs_extra_pins_microimpute_exactly():
    """Step 8 imputes with microimpute; a looser spec would resolve a newer release."""
    pins = [req for req in _extra("lfs") if req.name == "microimpute"]
    assert len(pins) == 1
    assert str(pins[0].specifier) == "==3.1.1"
