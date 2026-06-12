"""Restricted static cost: employer NICs relief only on recent NEET entrants.

Thin CLI wrapper around ``young_worker_nics.neet``: imputes each employed
21-24-year-old's probability of having been NEET within the past year from
LFS 5-quarter longitudinal panels (QRF main estimator plus an
earnings-banded sensitivity, both calibrated to the directly measured
entrant share), then multiplies each person's NICs saving by it.

Not part of the dashboard pipeline; exploratory analysis only.
"""

from __future__ import annotations

import argparse

import numpy as np
from microdf import MicroSeries

from young_worker_nics.formulas import exempt_employer_nics
from young_worker_nics.neet import build_neet_imputation
from young_worker_nics.sources import MARGINAL_AGE_LOWER, REFORM_AGE_UPPER, WEEKS_PER_YEAR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2027)
    parser.add_argument(
        "--lfs-path",
        nargs="+",
        required=True,
        help="One or more 5-quarter panel .tab files (e.g. ~/Downloads/UKDA-*-tab/tab/*.tab)",
    )
    parser.add_argument(
        "--neet",
        action="store_true",
        help="Kept for compatibility; the NEET imputation is now the only mode",
    )
    args = parser.parse_args()

    print("Loading PolicyEngine baseline...")
    from policyengine.tax_benefit_models.uk import managed_microsimulation

    baseline = managed_microsimulation()
    year = args.year

    class_1 = baseline.tax_benefit_system.parameters(
        f"{year}-01-01"
    ).gov.hmrc.national_insurance.class_1
    employer_rate = float(class_1.rates.employer)
    st = float(class_1.thresholds.secondary_threshold) * WEEKS_PER_YEAR
    ust = float(class_1.thresholds.upper_earnings_limit) * WEEKS_PER_YEAR

    age = baseline.calculate("age", year)
    employment_income = baseline.calculate("employment_income", year)
    ni_class_1_income = baseline.calculate("ni_class_1_income", year)
    saving = exempt_employer_nics(ni_class_1_income, st, ust, employer_rate)

    treated = (employment_income > 0) & (age >= MARGINAL_AGE_LOWER) & (age <= REFORM_AGE_UPPER)
    full_cost = float(saving[treated].sum())
    n_treated = float(treated.sum())
    print(
        f"\nFull static cost (all employed 21-24s): £{full_cost / 1e9:.2f}bn on {n_treated / 1e6:.2f}m employees"
    )

    treated_mask = np.asarray(treated.values, dtype=bool)
    person_weights = np.asarray(saving.weights)

    imputation = build_neet_imputation(args.lfs_path, baseline, year, treated_mask, person_weights)

    summary = imputation.panel_summary
    print(
        f"\nLFS panels: {summary['count']} files ({summary['studies']}), {summary['period']}, "
        f"{summary['total_respondents']} respondents"
    )
    print(
        f"Employed 21-24 donors: {summary['employed_21_24_donors']} "
        f"({summary['neet_entrants_21_24']} NEET entrants); "
        f"QRF training donors: {summary['qrf_training_donors']} "
        f"({summary['qrf_training_positives']} positives)"
    )
    print(
        f"Calibration target (weighted entrant share, employed 21-24): {imputation.entrant_share:.1%}"
    )

    scenarios = {
        "NEET per-person (QRF, calibrated)": imputation.probabilities,
        "NEET per-person (banded, calibrated)": imputation.banded_probabilities,
    }

    print(f"\n{'Scenario':45s} {'Cost £bn':>9s} {'% of full':>10s} {'Mean prob | treated':>20s}")
    for label, prob in scenarios.items():
        weighted_saving = saving * prob
        restricted = float(weighted_saving[treated].sum())
        mean_prob = float(
            MicroSeries(prob[treated_mask], weights=person_weights[treated_mask]).mean()
        )
        print(
            f"{label:45s} {restricted / 1e9:9.2f} {100 * restricted / full_cost:9.1f}% {mean_prob:19.1%}"
        )

        by_age = {}
        for a in range(MARGINAL_AGE_LOWER, REFORM_AGE_UPPER + 1):
            m = treated & (age == a)
            by_age[a] = float(weighted_saving[m].sum()) / 1e9
        print("  by age (£bn): " + ", ".join(f"{a}: {v:.3f}" for a, v in by_age.items()))


if __name__ == "__main__":
    main()
