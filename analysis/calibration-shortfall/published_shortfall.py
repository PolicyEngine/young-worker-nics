"""How far the published targeted population falls short of its own target.

Reads only ``data/young_worker_nics_results.json``, the published results,
and prints:

- the target the calibration aimed at (the LFS entrant share times the
  employed 21-24 population) next to the population it published;
- the static cost under two ways of closing the gap, plus the two references
  the results already carry (the earnings-banded sensitivity, and every
  treated employee at the entrant share).

The two gap-closing figures are scenarios, not bounds. A rerun with
probabilities moves the targeted mix as well as its size, so its cost can
land outside both; the target fixes only the targeted count in advance.

    python analysis/calibration-shortfall/published_shortfall.py
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "data" / "young_worker_nics_results.json"


def shortfall(results: dict) -> dict:
    everyone = results["reform"]["static"]
    targeted = results["targeted"]
    n_treated = everyone["n_marginal_employees"]
    cost_treated_bn = everyone["marginal_cost_bn"]
    n_published = targeted["static"]["n_marginal_employees"]
    cost_published_bn = targeted["static"]["marginal_cost_bn"]
    target_share = targeted["entrant_share"]

    published_share = n_published / n_treated
    n_target = target_share * n_treated
    missing = n_target - n_published
    # Average saving among treated employees the published run left at 0.
    left_out_saving = (cost_treated_bn - cost_published_bn) / (n_treated - n_published)
    return {
        "employed_21_24": n_treated,
        "target_share": target_share,
        "published_share": published_share,
        "published_vs_target": published_share / target_share - 1,
        "targeted_employees": {
            "published": n_published,
            "target": n_target,
            "missing": missing,
            "missing_vs_published": missing / n_published,
        },
        "static_cost_bn": {
            "published": cost_published_bn,
            "scenario_same_mix": cost_published_bn * n_target / n_published,
            "scenario_missing_spread_over_left_out": cost_published_bn + missing * left_out_saving,
            "reference_banded_sensitivity": targeted["sensitivity_banded_cost_bn"],
            "reference_everyone_at_target_share": target_share * cost_treated_bn,
        },
    }


def main() -> None:
    print(json.dumps(shortfall(json.loads(RESULTS.read_text())), indent=2))


if __name__ == "__main__":
    main()
