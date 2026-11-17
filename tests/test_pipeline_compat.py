"""Dataset selection in :func:`young_worker_nics.pipeline.run`, with the PolicyEngine
stack stubbed out so the test needs only the base install.

``run`` is public, so callers may build their own ``argparse.Namespace``; a Namespace
that uses the old field names must select the same dataset and year as before.
"""

import argparse
import importlib
import sys
import types

import pytest


class _DatasetChosen(Exception):
    """Raised by the stub simulation factory as soon as run() asks for a dataset."""


@pytest.fixture
def pipeline(monkeypatch):
    chosen: list[str | None] = []

    def managed_microsimulation(dataset=None, reform=None):
        chosen.append(dataset)
        raise _DatasetChosen

    stubs = {
        name: types.ModuleType(name)
        for name in (
            "policyengine",
            "policyengine.tax_benefit_models",
            "policyengine.tax_benefit_models.uk",
            "young_worker_nics.reform",
        )
    }
    stubs["policyengine.tax_benefit_models.uk"].managed_microsimulation = managed_microsimulation
    stubs["young_worker_nics.reform"].YOUNG_WORKER_EXEMPTION = object()
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(sys.modules, "young_worker_nics.pipeline", raising=False)
    yield importlib.import_module("young_worker_nics.pipeline"), chosen
    # Drop the copy bound to the stubs; monkeypatch then restores any earlier one.
    sys.modules.pop("young_worker_nics.pipeline", None)


def _dataset_chosen(module, chosen, args):
    with pytest.raises(_DatasetChosen):
        module.run(args)
    return chosen.pop()


def test_microcosm_fields_select_the_managed_dataset_and_year(pipeline):
    module, chosen = pipeline
    args = argparse.Namespace(microcosm=True, microcosm_year=2024, dataset=None)
    assert _dataset_chosen(module, chosen, args) == "populace_uk_2024"


def test_old_namespace_fields_still_work(pipeline):  # compat: populace alias, remove after 0.2.0
    module, chosen = pipeline
    old = argparse.Namespace(
        populace=True,  # compat: populace alias, remove after 0.2.0
        populace_year=2024,  # compat: populace alias, remove after 0.2.0
        dataset=None,
    )
    assert _dataset_chosen(module, chosen, old) == "populace_uk_2024"
    old = argparse.Namespace(
        populace=True,  # compat: populace alias, remove after 0.2.0
        dataset=None,
    )
    assert _dataset_chosen(module, chosen, old) == "populace_uk_2023"


def test_no_microcosm_field_uses_the_bundle_default(pipeline):
    module, chosen = pipeline
    assert _dataset_chosen(module, chosen, argparse.Namespace(dataset=None)) is None
