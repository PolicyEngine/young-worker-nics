"""Poverty and distributional impacts of the boosted-wage simulations.

Compares the baseline simulation with a reformed (boosted-wage) simulation
using PolicyEngine UK's household income and poverty definitions. Poverty is
the BHC *absolute* measure (`in_poverty_bhc`: equivalised HBAI household net
income below the DWP absolute low-income threshold, CPI-uprated), so the
poverty line is identical in baseline and reform by construction — we
deliberately avoid the relative 60%-of-median measure, whose line would
itself shift under the reform. Headcounts are person-weighted (people living
in households below the line), PolicyEngine's headline convention.

All aggregation is native microdf: ``calculate(..., map_to="person")``
returns person-weighted MicroSeries. Masks built on the baseline are applied
to the reformed sim's series positionally (``.values``) — person order is
identical across managed simulations — to avoid cross-simulation pandas
index alignment.
"""

from __future__ import annotations

from .sources import REFORM_AGE_LOWER, REFORM_AGE_UPPER


def poverty_impact(baseline, reformed, year: int, age) -> dict:
    """BHC absolute poverty, baseline vs reform: rates, 18-24 rates, headcounts."""
    young = ((age >= REFORM_AGE_LOWER) & (age <= REFORM_AGE_UPPER)).values

    base = baseline.calculate("in_poverty_bhc", year, map_to="person")
    ref = reformed.calculate("in_poverty_bhc", year, map_to="person")
    base_deep = baseline.calculate("in_deep_poverty_bhc", year, map_to="person")
    ref_deep = reformed.calculate("in_deep_poverty_bhc", year, map_to="person")

    return {
        "baseline_rate_bhc": float(base.mean()),
        "reformed_rate_bhc": float(ref.mean()),
        "baseline_rate_bhc_18_24": float(base[young].mean()),
        "reformed_rate_bhc_18_24": float(ref[young].mean()),
        "people_lifted": float(base.sum() - ref.sum()),
        "people_lifted_18_24": float(base[young].sum() - ref[young].sum()),
        "baseline_deep_rate_bhc": float(base_deep.mean()),
        "reformed_deep_rate_bhc": float(ref_deep.mean()),
    }


def inequality_impact(baseline, reformed, year: int) -> dict:
    """Gini of equivalised HBAI household net income, person-weighted.

    PolicyEngine's inequality convention: every person carries their
    household's equivalised net income; the Gini is computed over people.
    microdf's weighted ``.gini()`` does the aggregation natively.
    """
    base = baseline.calculate("equiv_hbai_household_net_income", year, map_to="person")
    ref = reformed.calculate("equiv_hbai_household_net_income", year, map_to="person")
    return {
        "baseline_gini": float(base.gini()),
        "reformed_gini": float(ref.gini()),
    }


GROUPINGS = {"deciles": 10, "quintiles": 5, "quartiles": 4}


def avg_change_by_group(baseline, reformed, year: int) -> dict:
    """Average household net-income change by baseline income group.

    For each grouping (deciles, quintiles, quartiles), households are ranked
    by BASELINE equivalised HBAI net income with person-weighted quantile
    boundaries — the same ranking convention as PolicyEngine's published
    decile charts — so group membership is fixed pre-reform. The average is
    the weighted mean change across ALL households in the group (gainers and
    non-gainers alike).
    """
    import numpy as np

    equiv_person = baseline.calculate("equiv_hbai_household_net_income", year, map_to="person")
    equiv_household = baseline.calculate("equiv_hbai_household_net_income", year)
    gain = reformed.calculate("household_net_income", year) - baseline.calculate(
        "household_net_income", year
    )

    out = {}
    for name, n_groups in GROUPINGS.items():
        quantiles = np.linspace(0, 1, n_groups + 1)[1:-1]
        boundaries = np.asarray(equiv_person.quantile(list(quantiles)))
        group_index = np.searchsorted(boundaries, equiv_household.values, side="right") + 1

        rows = []
        for g in range(1, n_groups + 1):
            mask = group_index == g
            g_gain = gain[mask]
            rows.append(
                {
                    "group": g,
                    "avg_change_per_household": float(g_gain.mean()),
                    "total_change_bn": float(g_gain.sum()) / 1e9,
                    "n_households": float(g_gain.count()),
                }
            )
        out[name] = rows
    return out
