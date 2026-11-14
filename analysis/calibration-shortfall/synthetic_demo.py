"""Show, on synthetic data, why Step 8's published calibration missed its target.

Step 8 imputes each employee's chance of being a recent NEET entrant, then
scales it so the weighted mean over employed 21-24-year-olds equals the
entrant share measured in the LFS. This script builds synthetic LFS-like
donors and FRS-like receivers and runs three versions of that step:

A. The published code (neet.py as of 30f5b65): microimpute 3.1.1's
   ``autoimpute(..., models=[QRF])`` on the float 0/1 target, then the
   published scale-then-clip formula.
B. The published formula's natural repair, solving for one factor under the
   clip, applied to A's output.
C. The fix in this branch: microcosm-fit's CategoricalClassifier
   probabilities, then the solved calibration.

It also checks the fix's one modelling choice. CategoricalClassifier's
boosted half reacts to the scale of its weights, so the fix fits on weights
normalised to mean 1; the last section measures how far the scale moves the
probabilities, and how close each scale gets to the true synthetic ones.

Part A needs microimpute 3.1.1, which the fix no longer installs:

    uv pip install -e ".[lfs]" "microimpute==3.1.1"
    python analysis/calibration-shortfall/synthetic_demo.py

Everything here is synthetic; no LFS or FRS record enters it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from young_worker_nics.neet import (  # noqa: E402
    PREDICTORS,
    _calibrate,
    _classifier_neet_probabilities,
    _weighted_mean,
)

SEED = 20261107
TARGET = "was_neet_recently"


def synthetic_donors(rng: np.random.Generator, n: int = 6256) -> pd.DataFrame:
    """LFS-like donors: employed at wave 5, aged 16-64, about 5% recent entrants."""
    age = rng.integers(16, 65, n).astype(float)
    gender = rng.choice(["MALE", "FEMALE"], n)
    pay = np.exp(9.6 + 0.04 * np.minimum(age - 16, 20) + rng.normal(0, 0.6, n))
    frame = pd.DataFrame({"age": age, "gender": gender, "employment_income": pay})
    frame[TARGET] = rng.random(n) < true_probability(frame)
    frame["weight"] = rng.lognormal(np.log(250), 0.5, n)
    return frame


def true_probability(people: pd.DataFrame) -> np.ndarray:
    """The synthetic P(entrant | age, gender, pay) the donors are drawn from."""
    logit = (
        -3.4
        - 0.07 * (people["age"].to_numpy() - 30)
        - 0.6 * (np.log(people["employment_income"].to_numpy()) - 10.2)
        + 0.15 * (people["gender"].to_numpy() == "MALE")
    )
    return 1 / (1 + np.exp(-logit))


def synthetic_receivers(rng: np.random.Generator, n: int = 40_000) -> pd.DataFrame:
    """FRS-like people of every age; about 60% of 16-64s employed."""
    age = rng.integers(0, 91, n).astype(float)
    gender = rng.choice(["MALE", "FEMALE"], n)
    employed = (age >= 16) & (age < 65) & (rng.random(n) < 0.6)
    log_pay = 9.6 + 0.04 * np.minimum(np.maximum(age - 16, 0), 20) + rng.normal(0, 0.6, n)
    return pd.DataFrame(
        {
            "age": age,
            "gender": gender,
            "employment_income": np.where(employed, np.exp(log_pay), 0.0),
            "person_weight": rng.lognormal(np.log(700), 0.4, n),
        }
    )


def published_formula(prob, treated, weights, target_share):
    """Step 8's calibration as published (30f5b65): scale by target / mean, then clip."""
    prob = np.where(treated, prob, 0.0)
    uncalibrated = _weighted_mean(prob[treated], weights[treated])
    return np.clip(prob * (target_share / uncalibrated), 0.0, 1.0)


def published_imputation(donor, receiver):
    """Step 8's imputation call as published (30f5b65), on microimpute 3.1.1."""
    from importlib.metadata import version

    from microimpute import QRF
    from microimpute.comparisons import autoimpute

    results = autoimpute(
        donor.assign(**{TARGET: donor[TARGET].astype(float)}),
        receiver[PREDICTORS],
        predictors=PREDICTORS,
        imputed_variables=[TARGET],
        weight_col="weight",
        models=[QRF],
        random_state=0,
    )
    # The package metadata, not microimpute.__version__, which 3.1.1 leaves at 1.1.2.
    return version("microimpute"), results.receiver_data[TARGET].clip(0, 1).to_numpy()


def share(prob, treated, weights) -> float:
    return _weighted_mean(prob[treated], weights[treated])


def weight_scale_checks(donor, receiver, treated, weights, target_share) -> dict:
    """How the donor weights' scale moves the classifier, and which scale fits better."""
    from microcosm.fit import CategoricalClassifier

    model = CategoricalClassifier(categorical_predictors=("gender",), seed=0)
    scaled = donor.assign(weight=donor["weight"] * 1000)
    as_given = [
        model.fit(d, PREDICTORS, [TARGET], weights=d["weight"].to_numpy()).predict_proba(
            receiver[PREDICTORS]
        )[treated, 1]
        for d in (donor, scaled)
    ]
    normalised = [
        _classifier_neet_probabilities(d, receiver, target_share, treated, weights)[treated]
        for d in (donor, scaled)
    ]
    errors = {"weights as given": [], "weights normalised to mean 1": []}
    for draw in range(5):
        fresh = synthetic_donors(np.random.default_rng(SEED + 1 + draw))
        held_out = synthetic_donors(np.random.default_rng(SEED + 100 + draw), n=50_000)
        truth = true_probability(held_out)
        raw = fresh["weight"].to_numpy()
        for label, fit_weights in zip(errors, (raw, raw / raw.mean()), strict=True):
            fitted = model.fit(fresh, PREDICTORS, [TARGET], weights=fit_weights)
            estimate = fitted.predict_proba(held_out[PREDICTORS])[:, 1]
            errors[label].append(float(np.sqrt(np.mean((estimate - truth) ** 2))))
    return {
        "max_change_when_every_donor_weight_grows_1000x": {
            "weights as given": float(np.max(np.abs(as_given[0] - as_given[1]))),
            "weights normalised to mean 1 (the fix)": float(
                np.max(np.abs(normalised[0] - normalised[1]))
            ),
        },
        "rmse_vs_true_probability_over_5_draws": {
            label: {"mean": float(np.mean(values)), "sd": float(np.std(values, ddof=1))}
            for label, values in errors.items()
        },
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    donor = synthetic_donors(rng)
    receiver = synthetic_receivers(rng)
    weights = receiver["person_weight"].to_numpy()
    treated = (
        (receiver["age"] >= 21) & (receiver["age"] <= 24) & (receiver["employment_income"] > 0)
    ).to_numpy()
    young = (donor["age"] >= 21) & (donor["age"] <= 24)
    target_share = _weighted_mean(
        donor.loc[young, TARGET].to_numpy(dtype=float), donor.loc[young, "weight"].to_numpy()
    )
    report: dict = {
        "donors": len(donor),
        "donor_entrants": int(donor[TARGET].sum()),
        "treated_receivers": int(treated.sum()),
        "target_share": target_share,
    }

    try:
        version, labels = published_imputation(donor, receiver)
    except ImportError:
        report["A_published"] = "skipped: microimpute is not installed"
        labels = None
    if labels is not None:
        published = published_formula(labels, treated, weights, target_share)
        report["A_published"] = {
            "microimpute": version,
            "distinct_imputed_values": sorted({float(v) for v in labels}),
            "share_before_calibration": share(labels, treated, weights),
            "share_after_calibration": share(published, treated, weights),
            "shortfall_vs_target": share(published, treated, weights) / target_share - 1,
        }
        try:
            _calibrate(labels, treated, weights, target_share)
            report["B_solved_on_labels"] = "reached the target"
        except ValueError as error:
            report["B_solved_on_labels"] = f"refused: {error}"

    fixed = _classifier_neet_probabilities(donor, receiver, target_share, treated, weights)
    report["C_fix"] = {
        "distinct_values_among_treated": int(len(np.unique(fixed[treated]))),
        "share_after_calibration": share(fixed, treated, weights),
        "gap_vs_target": share(fixed, treated, weights) - target_share,
        "treated_at_probability_1": int((fixed[treated] >= 1.0).sum()),
    }
    report["weight_scale"] = weight_scale_checks(donor, receiver, treated, weights, target_share)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
