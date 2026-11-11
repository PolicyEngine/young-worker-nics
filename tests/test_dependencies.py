"""Dependency pins that a rerun of Step 8 relies on."""

import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"
MICROCOSM = ("microcosm-fit", "microcosm-frame", "microcosm-graph")
PINNED = re.compile(
    r"^git\+https://github\.com/PolicyEngine/microcosm@([0-9a-f]{40})"
    r"#subdirectory=packages/([a-z-]+)$"
)


def _extra(name: str) -> dict[str, Requirement]:
    project = tomllib.loads(PYPROJECT.read_text())["project"]
    reqs = [Requirement(spec) for spec in project["optional-dependencies"][name]]
    return {canonicalize_name(req.name): req for req in reqs}


def test_lfs_extra_pins_microcosm_to_one_commit():
    """Step 8 fits Microcosm's classifier; a branch or tag would move under a rerun."""
    lfs = _extra("lfs")
    commits = set()
    for name in MICROCOSM:
        match = PINNED.match(lfs[name].url or "")
        assert match, f"{name} must install from a full commit of PolicyEngine/microcosm"
        assert match[2] == name
        commits.add(match[1])
    assert len(commits) == 1


def test_lfs_extra_drops_microimpute():
    """Step 8 no longer calls microimpute, which PolicyEngine archived on 2026-11-08."""
    assert "microimpute" not in _extra("lfs")
