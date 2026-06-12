"""Main young-worker NICs exemption pipeline.

Models extending the employer NICs zero rate — currently covering under-21s
(category M) and apprentices under 25 (category H) — to all employees aged
18 to 24, up to the Upper Secondary Threshold.

Because under-21s are already zero-rated in law, the marginal
(Exchequer-cost-relevant) population is 21-24-year-olds. The pipeline reports
both the headline 18-24 quantum and the marginal 21-24 cost. (Apprentices
under 25 are also exempt in law but are unobserved in the FRS and not
modelled, so the marginal cost is slightly overstated on that margin.)

Builds the dashboard JSON from the PolicyEngine (`policyengine.py`) bundle.
Wrapped as :func:`run` so it can be invoked from the package CLI
(:mod:`young_worker_nics.cli`) or imported directly.

All statutory parameters are read from the PolicyEngine parameter tree; every
other number comes from :mod:`young_worker_nics.sources`, which is emitted
verbatim into the results JSON so the dashboard renders no hardcoded numbers.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path

import numpy as np
from microdf import MicroSeries

from . import sources
from .calculator import build_person_calculator_lookup
from .formulas import employment_cost_reduction_pct, exempt_employer_nics
from .impacts import avg_change_by_group, inequality_impact, poverty_impact
from .reform import YOUNG_WORKER_EXEMPTION
from .sources import (
    MARGINAL_AGE_LOWER,
    REFORM_AGE_LOWER,
    REFORM_AGE_UPPER,
    WEEKS_PER_YEAR,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Enhanced-FRS calibration constrains age BANDS (10-19, 20-29), not single
# years of age, so single-age aggregates are statistically unidentified —
# weight slides freely between adjacent ages. Publish band-level breakdowns
# only. The 18-20 / 21-24 split is policy-motivated (the under-21 zero-rate
# boundary), which crosses the calibrated age-20 band edge — caveat carried
# into the JSON.
AGE_BANDS = [
    ("18-20", REFORM_AGE_LOWER, MARGINAL_AGE_LOWER - 1),
    ("21-24", MARGINAL_AGE_LOWER, REFORM_AGE_UPPER),
]

POPULATION_LABEL_FULL = "All employees aged 21-24"
POPULATION_LABEL_TARGETED = "Employees aged 21-24 who were NEET within the past year"


def _region_label(level: str) -> str:
    """ITL1 region enum to display label (EAST_OF_ENGLAND -> East of England)."""
    return level.replace("_", " ").title().replace(" Of ", " of ")


def _run_pass_through_scenarios(
    *,
    rates: list[float],
    boost_unit_values: np.ndarray,
    gross_cost: float,
    n_employees: float,
    simulation_factory,
    baseline,
    year: int,
    age,
    employment_income_values: np.ndarray,
    baseline_totals: dict[str, float],
    population_desc: str,
) -> list[dict]:
    """Boosted-wage pass-through scenarios for one treated population.

    Shared by the full 21-24 population and the targeted (recent-NEET)
    population, which differ only in the per-person wage boost.
    ``boost_unit_values`` is the unweighted person-order wage boost at 100%
    pass-through (zero outside the treated population); its survey-weighted
    total must equal ``gross_cost``, that population's static cost. Each
    non-zero rate re-runs a full PolicyEngine simulation on boosted wages, so
    income tax, employee NICs and benefit withdrawal are computed exactly
    person by person.

    Employer NICs on the wage increments are deliberately excluded: the
    reform zero-rates the relieved band, so the increments attract no
    employer NICs (`ni_employee` is Class 1 employee-side only). Student
    loan repayments also rise with earnings but are conservatively excluded
    from the offset. set_input MUST precede any calculate on the fresh sim:
    policyengine-core does not invalidate dependents' caches.
    """
    scenarios = []
    for index, s in enumerate(rates, start=1):
        if not 0.0 <= s <= 1.0:
            raise ValueError(f"Pass-through rate {s} outside [0, 1].")
        print(f"    [{index}/{len(rates)}] pass-through {s:.0%} ({population_desc})...")

        if s == 0:
            # No wages change: every offset is exactly zero and there is no
            # poverty or distributional impact to simulate (the no-change
            # case, not a fallback).
            scenarios.append(
                {
                    "pass_through_rate": 0.0,
                    "gross_cost_bn": gross_cost / 1e9,
                    "fiscal_offset_bn": 0.0,
                    "offset_components_bn": {
                        "income_tax": 0.0,
                        "employee_nics": 0.0,
                        "benefits_saved": 0.0,
                    },
                    "net_cost_bn": gross_cost / 1e9,
                    "avg_wage_gain": 0.0,
                    "poverty": None,
                    "inequality": None,
                    "avg_change_by_group": None,
                }
            )
            continue

        # Per-person gross wage boost: s × the population's per-person
        # employer NICs saving. Unweighted person-order array for set_input;
        # weights re-enter natively when the reformed sim's calculate returns
        # MicroSeries.
        boost_values = boost_unit_values * s
        expected_boost_total = gross_cost * s
        if expected_boost_total <= 0:
            raise RuntimeError(f"Pass-through {s} produced a zero total wage boost; check masks.")

        reformed = simulation_factory()
        reformed.set_input("employment_income", year, employment_income_values + boost_values)

        applied_boost_total = (
            float(reformed.calculate("employment_income", year).sum())
            - baseline_totals["employment_income"]
        )
        if abs(applied_boost_total - expected_boost_total) > 1e-6 * expected_boost_total:
            raise RuntimeError(
                "set_input did not take effect: applied weighted wage boost "
                f"£{applied_boost_total:,.0f} != expected £{expected_boost_total:,.0f}."
            )

        delta_income_tax = (
            float(reformed.calculate("income_tax", year).sum()) - baseline_totals["income_tax"]
        )
        delta_employee_nics = (
            float(reformed.calculate("ni_employee", year).sum()) - baseline_totals["ni_employee"]
        )
        benefits_saved = baseline_totals["household_benefits"] - float(
            reformed.calculate("household_benefits", year).sum()
        )

        fiscal_offset = delta_income_tax + delta_employee_nics + benefits_saved

        scenarios.append(
            {
                "pass_through_rate": s,
                "gross_cost_bn": gross_cost / 1e9,
                "fiscal_offset_bn": fiscal_offset / 1e9,
                "offset_components_bn": {
                    "income_tax": delta_income_tax / 1e9,
                    "employee_nics": delta_employee_nics / 1e9,
                    "benefits_saved": benefits_saved / 1e9,
                },
                "net_cost_bn": (gross_cost - fiscal_offset) / 1e9,
                # Weighted mean boost across the treated population — equals
                # the weighted boost total over the weighted employee count.
                "avg_wage_gain": expected_boost_total / n_employees,
                "poverty": poverty_impact(baseline, reformed, year, age),
                "inequality": inequality_impact(baseline, reformed, year),
                "avg_change_by_group": avg_change_by_group(baseline, reformed, year),
            }
        )
    return scenarios


def _employment_scenario_rows(
    elasticity_scenarios: list[tuple[str, float]],
    avg_wedge: float,
    n_employees: float,
    static_cost: float,
) -> list[dict]:
    """Labour-demand response rows: elasticity × cost wedge × employee count.

    Shared arithmetic for the full and targeted populations, which differ
    only in the (probability-)weighted employee count and average cost wedge.
    """
    rows = []
    for label, elasticity in elasticity_scenarios:
        employment_gain_pct = abs(elasticity) * avg_wedge
        new_jobs = employment_gain_pct * n_employees
        rows.append(
            {
                "scenario": label,
                "demand_elasticity": elasticity,
                "avg_cost_wedge_pct": avg_wedge,
                "employment_gain_pct": employment_gain_pct,
                "new_jobs": new_jobs,
                "static_cost_per_job": static_cost / new_jobs,
            }
        )
    return rows


def run(args: argparse.Namespace) -> None:
    """Run the pipeline end-to-end and write the dashboard JSON."""
    # ── Step 1: Load PolicyEngine baseline ──────────────────────────────────

    print("Step 1: Loading PolicyEngine baseline from the policyengine.py bundle ...")
    from policyengine.tax_benefit_models.uk import managed_microsimulation

    baseline = managed_microsimulation()
    YEAR = args.year

    # ── Step 2: Statutory parameters from the PolicyEngine parameter tree ───

    print("Step 2: Reading statutory NICs parameters...")
    _class_1 = baseline.tax_benefit_system.parameters(
        f"{YEAR}-01-01"
    ).gov.hmrc.national_insurance.class_1
    EMPLOYER_RATE = float(_class_1.rates.employer)
    SECONDARY_THRESHOLD = float(_class_1.thresholds.secondary_threshold) * WEEKS_PER_YEAR
    # The under-21 / apprentice Upper Secondary Thresholds are aligned with
    # the Upper Earnings Limit; PolicyEngine does not model the USTs
    # separately, so we read the UEL.
    UPPER_SECONDARY_THRESHOLD = float(_class_1.thresholds.upper_earnings_limit) * WEEKS_PER_YEAR
    print(
        f"    employer rate {EMPLOYER_RATE:.1%}, ST £{SECONDARY_THRESHOLD:,.0f}, "
        f"UST £{UPPER_SECONDARY_THRESHOLD:,.0f}"
    )

    # ── Step 3: Person-level baseline arrays ────────────────────────────────

    # `baseline.calculate` returns weighted MicroSeries; all sums/means below
    # are therefore population-weighted natively — no manual weight handling.
    print("Step 3: Calculating baseline person-level variables...")
    age = baseline.calculate("age", YEAR)
    gender = baseline.calculate("gender", YEAR)
    country = baseline.calculate("country", YEAR, map_to="person")
    region = baseline.calculate("region", YEAR, map_to="person")
    current_education = baseline.calculate("current_education", YEAR)
    employment_income = baseline.calculate("employment_income", YEAR)
    ni_class_1_income = baseline.calculate("ni_class_1_income", YEAR)
    ni_employer = baseline.calculate("ni_employer", YEAR)
    income_decile = baseline.calculate("household_income_decile", YEAR, map_to="person")

    is_employee = employment_income > 0
    in_reform_ages = (age >= REFORM_AGE_LOWER) & (age <= REFORM_AGE_UPPER)
    in_marginal_ages = (age >= MARGINAL_AGE_LOWER) & (age <= REFORM_AGE_UPPER)

    # NOTE: the PolicyEngine baseline does NOT model the existing under-21 /
    # apprentice zero rates, so baseline `ni_employer` is overstated for
    # under-21s. The marginal costing below restricts to ages 21-24, where the
    # model baseline is correct.

    # ── Step 4: Static cost ─────────────────────────────────────────────────

    print("Step 4: Static cost of the exemption...")
    saving_per_person = exempt_employer_nics(
        ni_class_1_income,
        SECONDARY_THRESHOLD,
        UPPER_SECONDARY_THRESHOLD,
        EMPLOYER_RATE,
    )
    assert hasattr(saving_per_person, "weights"), "formulas stripped MicroSeries weights"

    marginal_mask = is_employee & in_marginal_ages
    headline_mask = is_employee & in_reform_ages

    n_marginal = float(marginal_mask.sum())
    n_headline = float(headline_mask.sum())
    if n_marginal <= 0:
        raise RuntimeError("No weighted 21-24 employees found in baseline; cannot cost the reform.")

    static_cost_marginal = float(saving_per_person[marginal_mask].sum())
    static_cost_headline = float(saving_per_person[headline_mask].sum())

    # Cross-check: the same zero rate applied INSIDE the model via a
    # PolicyEngine Reform object must reproduce the threshold arithmetic to
    # within 0.1%, or the build fails. Baseline boolean masks index the
    # reformed MicroSeries positionally (.values): person order is identical
    # across managed simulations.
    print("    cross-checking against a PolicyEngine Reform-object simulation...")
    reform_sim = managed_microsimulation(reform=YOUNG_WORKER_EXEMPTION)
    reform_ni_employer = reform_sim.calculate("ni_employer", YEAR)
    reform_cost_marginal = float(ni_employer[marginal_mask].sum()) - float(
        reform_ni_employer[marginal_mask.values].sum()
    )
    reform_cost_headline = float(ni_employer[headline_mask].sum()) - float(
        reform_ni_employer[headline_mask.values].sum()
    )
    for label, formula_cost, reform_cost in [
        ("marginal 21-24", static_cost_marginal, reform_cost_marginal),
        ("headline 18-24", static_cost_headline, reform_cost_headline),
    ]:
        relative_error = abs(reform_cost - formula_cost) / abs(formula_cost)
        if relative_error > 1e-3:
            raise RuntimeError(
                f"Reform-object static cost diverges from threshold arithmetic ({label}): "
                f"£{reform_cost / 1e9:.4f}bn vs £{formula_cost / 1e9:.4f}bn "
                f"({relative_error:.3%} > 0.1% tolerance)."
            )
        print(f"    {label}: £{formula_cost / 1e9:.3f}bn — reform-object run matches.")

    print(f"    21-24 (marginal) static cost: £{static_cost_marginal / 1e9:.2f}bn")
    print(f"    18-24 headline quantum (incl. already-exempt): £{static_cost_headline / 1e9:.2f}bn")

    # ── Step 5: Breakdowns ──────────────────────────────────────────────────

    print("Step 5: Breakdowns by age band, gender, country, income decile...")

    def breakdown_row(label, level_mask):
        return {
            "group": str(label),
            "n_employees": float(level_mask.sum()),
            "static_cost_bn": float(saving_per_person[level_mask].sum()) / 1e9,
        }

    by_age_band = [
        breakdown_row(label, headline_mask & (age >= lo) & (age <= hi))
        for label, lo, hi in AGE_BANDS
    ]
    # Single years of age: indicative only — enhanced-FRS calibration
    # constrains 10-year bands, so weight can slide between adjacent ages
    # (see age_band_note in the output).
    by_age = [
        breakdown_row(a, headline_mask & (age == a))
        for a in range(REFORM_AGE_LOWER, REFORM_AGE_UPPER + 1)
    ]
    by_gender = [
        breakdown_row(level.replace("_", " ").title(), headline_mask & (gender == level))
        for level in sorted(set(gender[headline_mask]))
    ]
    by_country = sorted(
        (
            breakdown_row(level.replace("_", " ").title(), headline_mask & (country == level))
            for level in set(country[headline_mask])
        ),
        key=lambda row: row["static_cost_bn"],
        reverse=True,
    )
    by_region = sorted(
        (
            breakdown_row(_region_label(level), headline_mask & (region == level))
            for level in set(region[headline_mask])
        ),
        key=lambda row: row["static_cost_bn"],
        reverse=True,
    )
    by_income_decile = [
        breakdown_row(decile, headline_mask & (income_decile == decile)) for decile in range(1, 11)
    ]
    # Quintiles derive exactly from PolicyEngine's person-weighted deciles;
    # quartiles need their own person-weighted quantile boundaries on the same
    # income concept (equivalised HBAI household net income).
    by_income_quintile = [
        breakdown_row(q, headline_mask & (income_decile >= 2 * q - 1) & (income_decile <= 2 * q))
        for q in range(1, 6)
    ]
    equiv_person = baseline.calculate("equiv_hbai_household_net_income", YEAR, map_to="person")
    quartile_bounds = np.asarray(equiv_person.quantile([0.25, 0.5, 0.75]))
    quartile_index = np.searchsorted(quartile_bounds, equiv_person.values, side="right") + 1
    by_income_quartile = [
        breakdown_row(q, headline_mask & (quartile_index == q)) for q in range(1, 5)
    ]

    static_cost_18_20 = float(saving_per_person[headline_mask & (age < MARGINAL_AGE_LOWER)].sum())

    # ── Step 5b: Population reconciliation ──────────────────────────────────
    # Every 16-24-year-old is in education, in work, or in neither (NEET).
    # The model's "NEET proxy" (not in education and no employment income)
    # differs definitionally from the ONS LFS measure — see methods note.

    print("Step 5b: Population reconciliation (education / work / NEET)...")
    in_education = current_education != "NOT_IN_EDUCATION"

    def reconciliation_states(lo, hi):
        in_range = (age >= lo) & (age <= hi)
        pop = float(in_range.sum())
        return {
            "population": pop,
            "in_education": float((in_range & in_education).sum()),
            "in_education_not_working": float((in_range & in_education & ~is_employee).sum()),
            "in_employment": float((in_range & is_employee).sum()),
            "neet_proxy": float((in_range & ~in_education & ~is_employee).sum()),
            "neet_proxy_rate": float((in_range & ~in_education & ~is_employee).sum()) / pop,
        }

    neet_official = sources.OFFICIAL_STATS["neet"]
    reconciliation = {
        "model_16_24": reconciliation_states(16, REFORM_AGE_UPPER),
        "model_18_24": reconciliation_states(REFORM_AGE_LOWER, REFORM_AGE_UPPER),
        "official_16_24": {
            "neet_level": neet_official["level"],
            "neet_rate": neet_official["rate"],
            "population_implied": neet_official["level"] / neet_official["rate"],
            "period_label": neet_official["period_label"],
            "source": neet_official["source"],
        },
    }

    # ── Step 6: Pass-through scenarios (exact microsimulation) ──────────────
    # Net Exchequer cost if a share s of the employer saving is passed to
    # 21-24-year-old workers as higher gross wages. Scenario values and
    # citations live in sources.PASS_THROUGH_SCENARIOS; the simulation
    # machinery is shared with the targeted population in
    # _run_pass_through_scenarios.

    print("Step 6: Pass-through scenarios (exact microsimulation)...")
    employment_income_values = employment_income.values
    baseline_totals = {
        "employment_income": float(employment_income.sum()),
        "income_tax": float(baseline.calculate("income_tax", YEAR).sum()),
        "ni_employee": float(baseline.calculate("ni_employee", YEAR).sum()),
        "household_benefits": float(baseline.calculate("household_benefits", YEAR).sum()),
    }

    pass_through_scenarios = _run_pass_through_scenarios(
        rates=args.pass_through,
        boost_unit_values=np.where(marginal_mask.values, saving_per_person.values, 0.0),
        gross_cost=static_cost_marginal,
        n_employees=n_marginal,
        simulation_factory=managed_microsimulation,
        baseline=baseline,
        year=YEAR,
        age=age,
        employment_income_values=employment_income_values,
        baseline_totals=baseline_totals,
        population_desc="all employed 21-24s",
    )

    # ── Step 7: Labour demand (employment) response ────────────────────────
    # %Δ employment of treated 21-24s ≈ elasticity × %Δ employment cost.
    # Elasticity scenario values and citations live in
    # sources.DEMAND_ELASTICITIES.

    print("Step 7: Employment response scenarios...")
    wedge_mask = marginal_mask & (ni_class_1_income > 0)
    cost_wedge = employment_cost_reduction_pct(
        ni_class_1_income[wedge_mask],
        SECONDARY_THRESHOLD,
        UPPER_SECONDARY_THRESHOLD,
        EMPLOYER_RATE,
    )
    avg_wedge = float(cost_wedge.mean())
    elasticity_scenarios = [
        ("low", args.demand_elasticity_low),
        ("central", args.demand_elasticity_central),
        ("high", args.demand_elasticity_high),
    ]
    employment_scenarios = _employment_scenario_rows(
        elasticity_scenarios, avg_wedge, n_marginal, static_cost_marginal
    )

    # ── Step 8: Targeted population (opt-in: --lfs-path) ───────────────────
    # Second version of the reform results restricted to employed
    # 21-24-year-olds who were NEET within the past year, estimated from LFS
    # 5-quarter longitudinal panels via young_worker_nics.neet. Every
    # person-level quantity is weighted by the calibrated per-person
    # probability of being such a recent NEET entrant, rather than selecting
    # a discrete subsample.

    lfs_paths = args.lfs_path
    if lfs_paths:
        print("Step 8: Targeted population (employed 21-24s NEET within the past year)...")
        from .neet import build_neet_imputation

        person_weights = np.asarray(saving_per_person.weights, dtype=float)
        saving_values = np.asarray(saving_per_person.values, dtype=float)
        treated_values = np.asarray(marginal_mask.values, dtype=bool)

        print("    building the LFS NEET imputation (QRF, calibrated)...")
        imputation = build_neet_imputation(
            lfs_paths, baseline, YEAR, treated_values, person_weights
        )
        prob = np.asarray(imputation.probabilities, dtype=float)
        banded_prob = np.asarray(imputation.banded_probabilities, dtype=float)

        # Native MicroSeries arithmetic throughout: scaling a MicroSeries by
        # the per-person probability keeps survey weights attached, so every
        # aggregate below is the full-population aggregate with each person
        # contributing prob × their value.
        targeted_saving = saving_per_person * prob
        prob_count = MicroSeries(prob, weights=saving_per_person.weights)
        targeted_cost = float(targeted_saving[marginal_mask].sum())
        n_targeted = float(prob_count[marginal_mask].sum())
        if n_targeted <= 0 or targeted_cost <= 0:
            raise RuntimeError(
                "NEET imputation produced a zero probability-weighted targeted "
                "population; check the LFS panel files."
            )
        banded_cost = float((saving_per_person * banded_prob)[marginal_mask].sum())
        print(
            f"    targeted static cost: £{targeted_cost / 1e9:.2f}bn on "
            f"{n_targeted / 1e6:.2f}m probability-weighted employees "
            f"(banded sensitivity £{banded_cost / 1e9:.2f}bn)"
        )

        print("    targeted breakdowns (probability-weighted)...")

        def targeted_breakdown_row(label, level_mask):
            return {
                "group": str(label),
                "n_employees": float(prob_count[level_mask].sum()),
                "static_cost_bn": float(targeted_saving[level_mask].sum()) / 1e9,
            }

        # Probabilities are zero outside employed 21-24s, so reusing the
        # full-population group masks is exact: 18-20 rows are truthfully
        # zero (the targeted population contains no under-21s).
        targeted_by_age_band = [
            targeted_breakdown_row(label, headline_mask & (age >= lo) & (age <= hi))
            for label, lo, hi in AGE_BANDS
        ]
        targeted_by_age = [
            targeted_breakdown_row(a, headline_mask & (age == a))
            for a in range(REFORM_AGE_LOWER, REFORM_AGE_UPPER + 1)
        ]
        targeted_by_gender = [
            targeted_breakdown_row(
                level.replace("_", " ").title(), headline_mask & (gender == level)
            )
            for level in sorted(set(gender[headline_mask]))
        ]
        targeted_by_country = sorted(
            (
                targeted_breakdown_row(
                    level.replace("_", " ").title(), headline_mask & (country == level)
                )
                for level in set(country[headline_mask])
            ),
            key=lambda row: row["static_cost_bn"],
            reverse=True,
        )
        targeted_by_region = sorted(
            (
                targeted_breakdown_row(_region_label(level), headline_mask & (region == level))
                for level in set(region[headline_mask])
            ),
            key=lambda row: row["static_cost_bn"],
            reverse=True,
        )
        targeted_by_income_decile = [
            targeted_breakdown_row(decile, headline_mask & (income_decile == decile))
            for decile in range(1, 11)
        ]
        targeted_by_income_quintile = [
            targeted_breakdown_row(
                q, headline_mask & (income_decile >= 2 * q - 1) & (income_decile <= 2 * q)
            )
            for q in range(1, 6)
        ]
        targeted_by_income_quartile = [
            targeted_breakdown_row(q, headline_mask & (quartile_index == q)) for q in range(1, 5)
        ]

        # Pass-through: identical machinery, with each treated person's wage
        # boost scaled by their recent-NEET probability.
        print("    targeted pass-through scenarios (exact microsimulation)...")
        targeted_pass_through = _run_pass_through_scenarios(
            rates=args.pass_through,
            boost_unit_values=np.where(treated_values, saving_values * prob, 0.0),
            gross_cost=targeted_cost,
            n_employees=n_targeted,
            simulation_factory=managed_microsimulation,
            baseline=baseline,
            year=YEAR,
            age=age,
            employment_income_values=employment_income_values,
            baseline_totals=baseline_totals,
            population_desc="targeted recent-NEET 21-24s",
        )

        # Employment response: same arithmetic with the probability-weighted
        # employee count and probability-weighted average cost wedge.
        print("    targeted employment response scenarios...")
        # Probability-weighted mean wedge, natively: a MicroSeries whose
        # weights are w × P(recent NEET) over the NICs-liable 21-24s.
        wedge_mask_values = np.asarray(wedge_mask.values, dtype=bool)
        targeted_wedge_weights = (person_weights * prob)[wedge_mask_values]
        if targeted_wedge_weights.sum() <= 0:
            raise RuntimeError("Zero probability weight among NICs-liable 21-24 employees.")
        targeted_avg_wedge = float(
            MicroSeries(
                np.asarray(cost_wedge.values, dtype=float), weights=targeted_wedge_weights
            ).mean()
        )
        targeted_employment = _employment_scenario_rows(
            elasticity_scenarios, targeted_avg_wedge, n_targeted, targeted_cost
        )

        targeted = {
            "population_label": POPULATION_LABEL_TARGETED,
            "entrant_share": float(imputation.entrant_share),
            "lfs_panels": imputation.panel_summary,
            "sensitivity_banded_cost_bn": banded_cost / 1e9,
            "static": {
                "marginal_cost_bn": targeted_cost / 1e9,
                "n_marginal_employees": n_targeted,
                "avg_saving_per_employee": targeted_cost / n_targeted,
                "by_age_band": targeted_by_age_band,
                "by_age": targeted_by_age,
                "by_gender": targeted_by_gender,
                "by_country": targeted_by_country,
                "by_region": targeted_by_region,
                "by_income_decile": targeted_by_income_decile,
                "by_income_quintile": targeted_by_income_quintile,
                "by_income_quartile": targeted_by_income_quartile,
            },
            "pass_through": targeted_pass_through,
            "employment": targeted_employment,
        }
    else:
        print("Step 8: Targeted recent-NEET population skipped (pass --lfs-path to build it).")
        targeted = None

    # ── Step 9: Household calculator (opt-in: --include-calculator) ─────────

    if args.include_calculator:
        print("Step 9: Household calculator lookup...")
        person_calculator = build_person_calculator_lookup(
            year=YEAR,
            secondary_threshold=SECONDARY_THRESHOLD,
            upper_secondary_threshold=UPPER_SECONDARY_THRESHOLD,
            employer_rate=EMPLOYER_RATE,
            grid_min=args.grid_min,
            grid_max=args.grid_max,
            grid_count=args.grid_count,
            annual_rent=args.calculator_rent,
        )
    else:
        print("Step 9: Household calculator skipped (pass --include-calculator to build it).")
        person_calculator = None

    # ── Step 10: Write dashboard JSON ───────────────────────────────────────

    print("Step 10: Writing results JSON...")
    methods = {
        "static": (
            "Per person in PolicyEngine UK's enhanced-FRS microdata: the statutory "
            "employer rate times NICs-liable earnings between the Secondary and Upper "
            "Secondary Thresholds (both read from the PolicyEngine parameter tree), "
            "summed with survey weights. The marginal cost covers employed "
            "21-24-year-olds; under-21s are already exempt in law (category M)."
        ),
        "pass_through": (
            "For each pass-through rate s, every employed 21-24-year-old's wages rise "
            "by s times their employer NICs saving and the full microsimulation is "
            "re-run, so the fiscal offset (income tax, employee NICs, benefits saved) "
            "is simulated exactly. Student loan repayments are conservatively excluded."
        ),
        "poverty": (
            "Baseline and boosted-wage simulations compared on PolicyEngine's absolute "
            "before-housing-costs poverty measure: household equivalised HBAI net "
            "income against the CPI-uprated DWP threshold, counted across all people."
        ),
        "distributional": (
            "Households ranked by baseline equivalised HBAI net income into "
            "population deciles, quintiles or quartiles (PolicyEngine's published "
            "convention); the chart shows the average net-income change across "
            "all households in each group, gainers and non-gainers alike."
        ),
        "employment": (
            "External labour demand elasticities applied to the simulated percentage "
            "fall in total employment cost (gross pay plus employer NICs) for employed "
            "21-24-year-olds; new jobs equal elasticity times average cost wedge times "
            "the employee count. A partial-equilibrium scenario range, not a "
            "forecast."
        ),
        "reform_object": (
            "Build-time cross-check: the static cost is recomputed via a PolicyEngine "
            "Reform object that zero-rates the relieved band for 18-24s; the build "
            "fails if it diverges from the threshold arithmetic by more than 0.1%."
        ),
        "targeted_population": (
            "The targeted variant restricts the relief to employed 21-24-year-olds who "
            "were NEET within the past year, estimated from pooled LFS 5-quarter "
            "longitudinal panels (consecutive vintages follow disjoint entry cohorts, "
            "so pooling never double-counts a person). A panel member counts as a "
            "recent NEET entrant if they were NEET at any of waves 1-4 and employed at "
            "wave 5. A quantile regression forest imputes each enhanced-FRS employee's "
            "probability of being such an entrant from age, gender and earnings, with "
            "the mean calibrated to the directly measured entrant share among employed "
            "21-24 panel members. Every reform quantity then counts each employee at that "
            "probability rather than selecting a discrete subsample; the calibrated level is "
            "corroborated by the ONS X02 labour-market flows series."
        ),
    }

    output = {
        "year": YEAR,
        "fiscal_year_label": f"{YEAR}-{(YEAR + 1) % 100:02d}",
        # The policyengine[uk] bundle exact-pins policyengine-uk, so the
        # bundle version alone identifies the whole simulation stack.
        "package_versions": {"policyengine": importlib.metadata.version("policyengine")},
        "settings": {
            "pass_through_scenarios": list(args.pass_through),
            "demand_elasticities": {
                "low": args.demand_elasticity_low,
                "central": args.demand_elasticity_central,
                "high": args.demand_elasticity_high,
            },
            "lfs_paths": [str(p) for p in lfs_paths] if lfs_paths else None,
        },
        "methods": methods,
        "nics_parameters": {
            "employer_rate": EMPLOYER_RATE,
            "secondary_threshold_annual": SECONDARY_THRESHOLD,
            "upper_secondary_threshold_annual": UPPER_SECONDARY_THRESHOLD,
        },
        **sources.as_json(),
        "age_band_note": (
            "Enhanced-FRS calibration constrains 10-year age bands, not single "
            "years of age, so single-age figures are indicative and can shift "
            "between adjacent ages. The 18-20 / 21-24 split follows the "
            "under-21 zero-rate boundary and crosses the calibrated age-20 "
            "band edge."
        ),
        "baseline": {
            "n_employees_18_24": n_headline,
            "n_employees_21_24": n_marginal,
            "employer_nics_18_24_bn": float(ni_employer[headline_mask].sum()) / 1e9,
            "static_cost_18_20_bn": static_cost_18_20 / 1e9,
            "by_age_band": by_age_band,
            "reconciliation": reconciliation,
        },
        "reform": {
            "population_label": POPULATION_LABEL_FULL,
            "static": {
                "marginal_cost_bn": static_cost_marginal / 1e9,
                "headline_quantum_bn": static_cost_headline / 1e9,
                "n_marginal_employees": n_marginal,
                "avg_saving_per_employee": static_cost_marginal / n_marginal,
                "by_age_band": by_age_band,
                "by_age": by_age,
                "by_gender": by_gender,
                "by_country": by_country,
                "by_region": by_region,
                "by_income_decile": by_income_decile,
                "by_income_quintile": by_income_quintile,
                "by_income_quartile": by_income_quartile,
            },
            "pass_through": pass_through_scenarios,
            "employment": employment_scenarios,
        },
        "targeted": targeted,
        "person_calculator": person_calculator,
    }

    for destination in [
        REPO_ROOT / "data" / "young_worker_nics_results.json",
        REPO_ROOT / "dashboard" / "public" / "data" / "young_worker_nics_results.json",
    ]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(output, indent=2, default=str))
        print(f"    wrote {destination}")

    print("Done.")
