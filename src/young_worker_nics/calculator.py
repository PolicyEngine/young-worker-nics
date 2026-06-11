"""Single-worker calculator: what the exemption is worth for one young employee.

Sweeps employment income for a synthetic young worker and stores, per gross
salary point, the employer NICs saved, the worker's baseline net income and
benefits, and the exact net gain if the saving were fully passed through as
wages (computed with a second PolicyEngine call at the boosted income, so
there is no interpolation error and no grid-edge clamping).

Profiles cover the variables that change the shape of the curves: age
(Universal Credit eligibility, minimum wage bands), location (Scotland has
different income tax), and private-renter status (UC housing element). Uses
the unified ``policyengine`` (policyengine.py) package household entry point,
``pe.uk.calculate_household``; policyengine.py has no parametric ``axes``
sweep for households, so the grid is sampled point by point.
"""

from __future__ import annotations

import numpy as np

from .formulas import exempt_employer_nics
from .sources import CALCULATOR_ANNUAL_RENT, REFORM_AGE_LOWER, REFORM_AGE_UPPER

AGES = list(range(REFORM_AGE_LOWER, REFORM_AGE_UPPER + 1))

# region group (rUK vs Scotland — different income tax) × renter.
# NORTH_EAST stands in for the rest of the UK: for a single synthetic worker
# with rent fixed by assumption, region affects nothing else material.
REGION_SPECS = {
    "ruk": "NORTH_EAST",
    "scotland": "SCOTLAND",
}
RENTER_SPECS = {0: False, 1: True}


def _household_spec(region: str, renter: bool, annual_rent: float) -> dict:
    household = {"region": region}
    if renter:
        household["tenure_type"] = "RENT_PRIVATELY"
        household["rent"] = annual_rent
    return household


def _calculate_point(year: int, age: int, household: dict, gross: float) -> dict[str, float]:
    import policyengine as pe

    result = pe.uk.calculate_household(
        people=[{"age": age, "employment_income": float(gross)}],
        household=household,
        year=year,
    )
    return {
        "net": float(result.household.household_net_income),
        "benefits": float(result.household.household_benefits),
    }


def build_person_calculator_lookup(
    year: int,
    secondary_threshold: float,
    upper_secondary_threshold: float,
    employer_rate: float,
    grid_min: float,
    grid_max: float,
    grid_count: int,
    annual_rent: float = CALCULATOR_ANNUAL_RENT.value,
) -> dict:
    """Curves per profile (age × region × renter): baseline net income and
    benefits, the employer NICs saving, and the exact net gain under full
    pass-through at each grid point."""
    gross_grid = np.linspace(grid_min, grid_max, grid_count)
    employer_saving = exempt_employer_nics(
        gross_grid, secondary_threshold, upper_secondary_threshold, employer_rate
    )

    profiles = {}
    for age in AGES:
        for region_key, region in REGION_SPECS.items():
            for rent_key, renter in RENTER_SPECS.items():
                key = f"age{age}|{region_key}|rent{rent_key}"
                household = _household_spec(region, renter, annual_rent)

                net, benefits, net_boosted = [], [], []
                for gross, saving in zip(gross_grid, employer_saving, strict=True):
                    base = _calculate_point(year, age, household, gross)
                    boosted = _calculate_point(year, age, household, gross + saving)
                    net.append(base["net"])
                    benefits.append(base["benefits"])
                    net_boosted.append(boosted["net"])

                profiles[key] = {
                    "employment_income": gross_grid.tolist(),
                    "net": net,
                    "benefits": benefits,
                    "employer_nics_saving": employer_saving.tolist(),
                    "net_gain_full_passthrough": (np.array(net_boosted) - np.array(net)).tolist(),
                }

    return {
        "ages": AGES,
        "regions": {k: v for k, v in REGION_SPECS.items()},
        "annual_rent": annual_rent,
        "grid": {"min": grid_min, "max": grid_max, "count": grid_count},
        "profiles": profiles,
    }
