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
import json
from pathlib import Path

import numpy as np

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
    # 21-24-year-old workers as higher gross wages. Each non-zero scenario
    # re-runs a full PolicyEngine simulation on boosted wages, so income tax,
    # employee NICs and benefit withdrawal are computed exactly person by
    # person. Scenario values and citations live in
    # sources.PASS_THROUGH_SCENARIOS.
    #
    # Employer NICs on the wage increments are deliberately excluded: the
    # reform zero-rates the relieved band, so the increments attract no
    # employer NICs (`ni_employee` is Class 1 employee-side only). Student
    # loan repayments also rise with earnings but are conservatively excluded
    # from the offset. set_input MUST precede any calculate on the fresh sim:
    # policyengine-core does not invalidate dependents' caches.

    print("Step 6: Pass-through scenarios (exact microsimulation)...")
    employment_income_values = employment_income.values
    baseline_employment_income_total = float(employment_income.sum())
    baseline_income_tax_total = float(baseline.calculate("income_tax", YEAR).sum())
    baseline_employee_nics_total = float(baseline.calculate("ni_employee", YEAR).sum())
    baseline_benefits_total = float(baseline.calculate("household_benefits", YEAR).sum())

    pass_through_scenarios = []
    for index, s in enumerate(args.pass_through, start=1):
        if not 0.0 <= s <= 1.0:
            raise ValueError(f"Pass-through rate {s} outside [0, 1].")
        print(f"    [{index}/{len(args.pass_through)}] pass-through {s:.0%}...")

        if s == 0:
            # No wages change: every offset is exactly zero and there is no
            # poverty or distributional impact to simulate (the no-change
            # case, not a fallback).
            pass_through_scenarios.append(
                {
                    "pass_through_rate": 0.0,
                    "gross_cost_bn": static_cost_marginal / 1e9,
                    "fiscal_offset_bn": 0.0,
                    "offset_components_bn": {
                        "income_tax": 0.0,
                        "employee_nics": 0.0,
                        "benefits_saved": 0.0,
                    },
                    "net_cost_bn": static_cost_marginal / 1e9,
                    "avg_wage_gain": 0.0,
                    "poverty": None,
                    "inequality": None,
                    "avg_change_by_group": None,
                }
            )
            continue

        # Per-person gross wage boost: s × employer NICs saving, employed
        # 21-24s only. Unweighted person-order array for set_input; weights
        # re-enter natively when the reformed sim's calculate returns
        # MicroSeries.
        boost = saving_per_person * s
        boost_values = np.where(marginal_mask.values, boost.values, 0.0)
        expected_boost_total = float(boost[marginal_mask].sum())
        if expected_boost_total <= 0:
            raise RuntimeError(f"Pass-through {s} produced a zero total wage boost; check masks.")

        reformed = managed_microsimulation()
        reformed.set_input("employment_income", YEAR, employment_income_values + boost_values)

        applied_boost_total = (
            float(reformed.calculate("employment_income", YEAR).sum())
            - baseline_employment_income_total
        )
        if abs(applied_boost_total - expected_boost_total) > 1e-6 * expected_boost_total:
            raise RuntimeError(
                "set_input did not take effect: applied weighted wage boost "
                f"£{applied_boost_total:,.0f} != expected £{expected_boost_total:,.0f}."
            )

        delta_income_tax = (
            float(reformed.calculate("income_tax", YEAR).sum()) - baseline_income_tax_total
        )
        delta_employee_nics = (
            float(reformed.calculate("ni_employee", YEAR).sum()) - baseline_employee_nics_total
        )
        benefits_saved = baseline_benefits_total - float(
            reformed.calculate("household_benefits", YEAR).sum()
        )

        fiscal_offset = delta_income_tax + delta_employee_nics + benefits_saved

        pass_through_scenarios.append(
            {
                "pass_through_rate": s,
                "gross_cost_bn": static_cost_marginal / 1e9,
                "fiscal_offset_bn": fiscal_offset / 1e9,
                "offset_components_bn": {
                    "income_tax": delta_income_tax / 1e9,
                    "employee_nics": delta_employee_nics / 1e9,
                    "benefits_saved": benefits_saved / 1e9,
                },
                "net_cost_bn": (static_cost_marginal - fiscal_offset) / 1e9,
                "avg_wage_gain": float(boost[marginal_mask].mean()),
                "poverty": poverty_impact(baseline, reformed, YEAR, age),
                "inequality": inequality_impact(baseline, reformed, YEAR),
                "avg_change_by_group": avg_change_by_group(baseline, reformed, YEAR),
            }
        )

    # ── Step 7: Labour demand (employment) response ────────────────────────
    # %Δ employment of treated 21-24s ≈ elasticity × %Δ employment cost.
    # Elasticity scenario values and citations live in
    # sources.DEMAND_ELASTICITIES.

    print("Step 7: Employment response scenarios...")
    wedge_mask = marginal_mask & (ni_class_1_income > 0)
    avg_wedge = float(
        employment_cost_reduction_pct(
            ni_class_1_income[wedge_mask],
            SECONDARY_THRESHOLD,
            UPPER_SECONDARY_THRESHOLD,
            EMPLOYER_RATE,
        ).mean()
    )
    employment_scenarios = []
    for label, elasticity in [
        ("low", args.demand_elasticity_low),
        ("central", args.demand_elasticity_central),
        ("high", args.demand_elasticity_high),
    ]:
        employment_gain_pct = abs(elasticity) * avg_wedge
        new_jobs = employment_gain_pct * n_marginal
        employment_scenarios.append(
            {
                "scenario": label,
                "demand_elasticity": elasticity,
                "avg_cost_wedge_pct": avg_wedge,
                "employment_gain_pct": employment_gain_pct,
                "new_jobs": new_jobs,
                "static_cost_per_job": static_cost_marginal / new_jobs,
            }
        )

    # ── Step 8: Household calculator (opt-in: --include-calculator) ─────────

    if args.include_calculator:
        print("Step 8: Household calculator lookup...")
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
        print("Step 8: Household calculator skipped (pass --include-calculator to build it).")
        person_calculator = None

    # ── Step 9: Write dashboard JSON ────────────────────────────────────────

    print("Step 9: Writing results JSON...")
    methods = {
        "static": (
            "For each employed person in PolicyEngine UK's enhanced-FRS microdata, the "
            "employer NICs forgone equal NICs-liable earnings between the Secondary Threshold "
            "and the Upper Secondary Threshold (both read from the PolicyEngine parameter "
            "tree) times the statutory employer rate, summed with survey weights. The marginal "
            "cost covers employed 21-24-year-olds; the 18-24 headline quantum additionally "
            "counts under-21s, who are already exempt in law (category M) and carry no "
            "marginal Exchequer cost."
        ),
        "pass_through": (
            "For each pass-through rate s, every employed 21-24-year-old's employment income "
            "is raised by s times their employer NICs saving and a full PolicyEngine "
            "microsimulation is re-run on the boosted wages. The fiscal offset is the exact "
            "simulated change in income tax plus employee NICs plus benefits saved. "
            "Employer NICs on the wage "
            "increments are excluded because the reform exempts the relieved band; student "
            "loan repayments, which also rise with earnings, are conservatively excluded."
        ),
        "poverty": (
            "Poverty impacts compare the baseline simulation with each boosted-wage "
            "simulation on PolicyEngine's before-housing-costs absolute poverty measure: a "
            "person counts as in poverty if their household's equivalised HBAI net income "
            "falls below the DWP absolute low-income threshold (CPI-uprated), with "
            "person-weighted headcounts. Deep poverty uses half that threshold. Because the "
            "line is an absolute parameter rather than a within-simulation median, it is "
            "identical in baseline and reform by construction. The zero-pass-through central "
            "case changes no wages, so it has no poverty impact."
        ),
        "distributional": (
            "Distributional impacts compare household net income between the baseline and "
            "each boosted-wage simulation. Households are ranked by baseline equivalised "
            "HBAI net income with person-weighted quantile boundaries (PolicyEngine's "
            "published convention) into deciles, quintiles or quartiles; the chart shows "
            "the weighted average change across all households in each group, gainers and "
            "non-gainers alike. The Gini index is computed over people, each carrying "
            "their household's equivalised net income, in baseline and reform."
        ),
        "employment": (
            "Employment effects apply external labour demand elasticities to the simulated "
            "percentage fall in total employment cost (gross pay plus employer NICs) for "
            "employed 21-24-year-olds; new jobs equal the elasticity times the average cost "
            "wedge times the weighted employee count. This is a partial-equilibrium scenario "
            "range, not a forecast, and is independent of the pass-through scenarios. "
            "Elasticity values and citations are in the assumptions block."
        ),
        "reform_object": (
            "As a build-time cross-check, the static cost is recomputed by passing a "
            "PolicyEngine Reform object that zero-rates employer NICs between the Secondary "
            "and Upper Secondary Thresholds for ages 18-24, and differencing the simulated "
            "employer NICs against baseline on the same masks. The build fails if this "
            "diverges from the direct threshold arithmetic by more than 0.1%."
        ),
        "reconciliation": (
            "Every young person is in exactly one of three states: in education, in "
            "employment, or in neither (NEET). Model counts come from the enhanced FRS: "
            "'in education' is a current education status other than NOT_IN_EDUCATION, "
            "'in employment' is any employment income in the year (so working students "
            "appear in both), and the NEET proxy is people in neither. This proxy differs "
            "from the ONS LFS measure, which is a point-in-time status that also counts "
            "training, so the model understates the official NEET level; the model's "
            "16-24 population also runs below the ONS-implied total because the FRS "
            "calibration targets broad age bands rather than this age range exactly. The "
            "NEET figure is who the policy is FOR; the employee figure is who the "
            "exemption is PAID ON — the gap between them is why much of a blanket "
            "hiring subsidy goes to employment that would exist anyway."
        ),
    }

    output = {
        "year": YEAR,
        "fiscal_year_label": f"{YEAR}-{(YEAR + 1) % 100:02d}",
        "settings": {
            "pass_through_scenarios": list(args.pass_through),
            "demand_elasticities": {
                "low": args.demand_elasticity_low,
                "central": args.demand_elasticity_central,
                "high": args.demand_elasticity_high,
            },
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
            "years of age, so single-age figures are indicative — weight can "
            "slide between adjacent ages. The 18-20 / 21-24 split follows the "
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
            "static": {
                "marginal_cost_bn": static_cost_marginal / 1e9,
                "headline_quantum_bn": static_cost_headline / 1e9,
                "n_marginal_employees": n_marginal,
                "avg_saving_per_employee": static_cost_marginal / n_marginal,
                "by_age_band": by_age_band,
                "by_age": by_age,
                "by_gender": by_gender,
                "by_country": by_country,
                "by_income_decile": by_income_decile,
                "by_income_quintile": by_income_quintile,
                "by_income_quartile": by_income_quartile,
            },
            "pass_through": pass_through_scenarios,
            "employment": employment_scenarios,
        },
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
