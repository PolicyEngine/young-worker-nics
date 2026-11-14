"""NEET-history imputation from LFS five-quarter longitudinal panels.

Estimates each employed 21-24-year-old's probability of having been NEET
(non-employed and not enrolled as a student) at some point in the past year,
from LFS panel members observed NEET at any of waves 1-4 and employed at
wave 5. A weighted classifier (microcosm-fit's CategoricalClassifier)
learns that probability over age, gender and earnings; an earnings-banded
estimator provides a sensitivity. Calibration scales both so the weighted
mean among treated employees equals the directly measured, survey-weighted
entrant share among employed 21-24 LFS donors: the level then rests on the
LFS group rate, so dropping missing-pay donors cannot bias it. Caveat: the
stacked panels hold only a few hundred employed 21-24 donors, so cell rates
are noisy — the calibrated level is more reliable than any single band.
``CLASSIFIER_SEED`` seeds the classifier's boosted learner (its spline logit
draws nothing at random), so a rerun on the same panels and package
versions repeats the probabilities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from microdf import MicroSeries

from .sources import (
    LFS_ADULT_AGE_FLOOR,
    MARGINAL_AGE_LOWER,
    REFORM_AGE_UPPER,
    WORKING_AGE_CEILING,
)


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """Survey-weighted mean via native microdf, never manual weight arithmetic."""
    return float(MicroSeries(np.asarray(values, dtype=float), weights=weights).mean())


INCAC_COLS = [f"INCAC05{q}" for q in range(1, 6)]
ENROLL_COLS = [f"ENROLL{q}" for q in range(1, 6)]

PREDICTORS = ["age", "gender", "employment_income"]
CLASSIFIER_SEED = 0

_PERIOD_RE = re.compile(r"5q_(jm|aj|js|od)(\d{2})_(jm|aj|js|od)(\d{2})", re.IGNORECASE)
_STUDY_RE = re.compile(r"UKDA[-_ ](\d+)", re.IGNORECASE)
_QUARTER_LABELS = {"jm": "Jan-Mar", "aj": "Apr-Jun", "js": "Jul-Sep", "od": "Oct-Dec"}
_QUARTER_ORDER = {"jm": 1, "aj": 2, "js": 3, "od": 4}


@dataclass
class NeetImputation:
    probabilities: np.ndarray
    banded_probabilities: np.ndarray
    entrant_share: float
    panel_summary: dict


def load_panels(lfs_paths: list[str]) -> pd.DataFrame:
    """Load and stack one or more 5-quarter panel vintages.

    Consecutive vintages follow disjoint entry cohorts, so stacking never
    counts a person twice. The longitudinal weight is named per vintage
    (LGWT22, LGWT23, ...); it is auto-detected and renamed to LGWT.
    """
    frames = []
    for path in lfs_paths:
        panel = pd.read_csv(path, sep="\t")
        weight_cols = [c for c in panel.columns if c.upper().startswith("LGWT")]
        if len(weight_cols) != 1:
            raise ValueError(f"{path}: expected one LGWT* weight column, found {weight_cols}")
        frames.append(panel.rename(columns={weight_cols[0]: "LGWT"}))
    return pd.concat(frames, ignore_index=True)


def derive_period(lfs_paths: list[str]) -> str:
    """Span of the stacked panels, parsed from filename date codes."""
    starts, ends = [], []
    for path in lfs_paths:
        match = _PERIOD_RE.search(Path(path).name.lower())
        if not match:
            raise ValueError(f"Cannot parse the panel period from filename: {Path(path).name}")
        starts.append((2000 + int(match[2]), _QUARTER_ORDER[match[1]], match[1]))
        ends.append((2000 + int(match[4]), _QUARTER_ORDER[match[3]], match[3]))
    start, end = min(starts), max(ends)
    return f"{_QUARTER_LABELS[start[2]]} {start[0]} to {_QUARTER_LABELS[end[2]]} {end[0]}"


def derive_studies(lfs_paths: list[str]) -> str:
    """UKDA study numbers parsed from the file paths, e.g. 'UKDA SN 9133, 9482'.

    The study number is taken from a ``UKDA-<n>`` segment in the path (the
    UK Data Service download layout). When the panels have been copied out of
    that layout the number is unavailable; rather than fail the whole build
    over a metadata label, fall back to naming the panel files. The label is
    descriptive only and is not used in any computation."""
    numbers = set()
    for path in lfs_paths:
        match = _STUDY_RE.search(str(path))
        if match:
            numbers.add(int(match[1]))
    if numbers:
        return "UKDA SN " + ", ".join(str(n) for n in sorted(numbers))
    panels = ", ".join(sorted(Path(p).stem for p in lfs_paths))
    return f"UK Data Service LFS five-quarter longitudinal panels ({panels})"


def neet_transition_targets(panel: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Per person-row: (employed at wave 5, NEET at any of waves 1-4).

    NEET means non-employed (INCAC05q >= 5) and not an enrolled student
    (ENROLLq != 1). Employed at wave 5 means INCAC055 in 1..4.
    """
    inc = panel[INCAC_COLS].to_numpy()
    enr = panel[ENROLL_COLS].to_numpy()
    employed_w5 = (inc[:, 4] >= 1) & (inc[:, 4] <= 4)
    was_neet = ((inc[:, :4] >= 5) & (enr[:, :4] != 1)).any(axis=1)
    return employed_w5, was_neet


def annualise_pay(weekly_pay: np.ndarray, weeks_in_year: float) -> np.ndarray:
    """Annual gross pay; negative sentinels (GRSSWK5 < 0) are missing, never £0.

    ``weeks_in_year`` is PolicyEngine's WEEKS_IN_YEAR, supplied by the caller so
    this module stays import-safe without policyengine_uk (pure-Python tests).
    """
    weekly_pay = np.asarray(weekly_pay, dtype=float)
    return np.where(weekly_pay >= 0, weekly_pay * weeks_in_year, np.nan)


#: Bisection steps for the calibration factor's logarithm. Each step halves the
#: bracket, which spans at most about 750, so it closes to adjacent floats in
#: about 65 steps.
_CALIBRATION_STEPS = 200
#: Slack for rounding when the target equals the most any factor can reach.
_SHARE_TOLERANCE = 1e-12


def _calibrate(
    prob: np.ndarray,
    treated_mask: np.ndarray,
    person_weights: np.ndarray,
    target_share: float,
) -> np.ndarray:
    """Scale treated probabilities by one factor so their weighted mean hits the target.

    Each treated person gets ``min(f * p, 1)`` for the one factor ``f`` that
    makes the weighted mean over treated people equal ``target_share``;
    everyone else gets 0. When no scaled probability reaches 1, ``f`` is the
    plain ratio ``target_share / mean(p)`` and the result equals scaling and
    clipping. When some do reach 1, clipping them alone would leave the mean
    short of the target, so ``f`` grows until the people below 1 make up the
    difference. The weighted mean of ``min(f * p, 1)`` rises continuously in
    ``f``, so bisection finds it. The bisection runs over ``log f``: the
    bracket can span hundreds of orders of magnitude, and when some
    probabilities are subnormal, ``f`` itself can exceed the largest float.

    Raises:
        ValueError: If a treated probability lies outside [0, 1], a treated
            weight is negative or non-finite, the treated weights sum to zero,
            the target lies outside [0, 1], no treated person with a positive
            weight has a nonzero probability, or the target exceeds the
            weighted share of treated people with a nonzero probability (the
            most any factor reaches). The last one means the imputation
            returned too few nonzero values, as 0/1 class labels do.
    """
    treated_mask = np.asarray(treated_mask, dtype=bool)
    prob = np.where(treated_mask, np.asarray(prob, dtype=float), 0.0)
    p = prob[treated_mask]
    w = np.asarray(person_weights, dtype=float)[treated_mask]
    if not (np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()):
        raise ValueError("Imputed probabilities must lie in [0, 1] for treated people.")
    if not (np.isfinite(w).all() and (w >= 0).all() and w.sum() > 0):
        raise ValueError("Treated person weights must be finite, non-negative and not all zero.")
    if not 0.0 <= target_share <= 1.0:
        raise ValueError(f"The target share must lie in [0, 1], not {target_share}.")
    reachable = _weighted_mean((p > 0).astype(float), w)
    if reachable <= 0:
        raise ValueError(
            "Imputed probabilities are zero across the treated population; "
            "cannot calibrate to the measured entrant share."
        )
    if target_share == 0.0:
        return prob * 0.0
    uncalibrated = _weighted_mean(p, w)
    # A subnormal weighted mean, or a subnormal weighted sum behind it, has
    # lost precision, so the factor comes straight from the mean only when
    # both are normal floats.
    weighted_total = float(MicroSeries(p, weights=w).sum())
    if min(uncalibrated, weighted_total) >= np.finfo(float).tiny:
        factor = target_share / uncalibrated
        if factor * p.max() <= 1.0:
            return prob * factor

    if target_share > reachable + _SHARE_TOLERANCE:
        raise ValueError(
            f"No scaling of the imputed probabilities reaches the target share "
            f"{target_share:.6f}: only {reachable:.6f} of the treated weight has a "
            "nonzero probability. 0/1 class labels in place of probabilities do this."
        )
    positive = p > 0
    log_p = np.full(p.shape, -np.inf)
    log_p[positive] = np.log(p[positive])

    def scaled(log_factor: float) -> np.ndarray:
        """``min(f * p, 1)`` for ``f = exp(log_factor)``, without overflow."""
        with np.errstate(over="ignore"):
            factor = np.exp(log_factor)
        if np.isfinite(factor):
            # p <= 1, so p * factor stays finite, and 0 * factor stays 0.
            return np.minimum(p * factor, 1.0)
        return np.exp(np.minimum(log_p + log_factor, 0.0))

    # The weighted mean of min(f * p, 1) never exceeds f * max(p), so the
    # factor that hits the target is at least target / max(p). At ``high``,
    # every nonzero p scales past 1, so the mean reaches every reachable share.
    low = float(np.log(target_share) - log_p.max())
    high = float(1.0 - log_p[positive].min())
    for _ in range(_CALIBRATION_STEPS):
        middle = 0.5 * (low + high)
        if middle <= low or middle >= high:
            break
        if _weighted_mean(scaled(middle), w) < target_share:
            low = middle
        else:
            high = middle
    calibrated = np.zeros_like(prob)
    calibrated[treated_mask] = scaled(high)
    return calibrated


def banded_neet_probabilities(
    donor_annual_pay: np.ndarray,
    donor_was_neet: np.ndarray,
    donor_weights: np.ndarray,
    target_share: float,
    employment_income: np.ndarray,
    treated_mask: np.ndarray,
    person_weights: np.ndarray,
) -> np.ndarray:
    """Earnings-banded sensitivity estimator.

    The earnings GRADIENT comes from weighted entrant rates by observed-pay
    tercile among the donors; receivers are mapped through the same cutoffs.
    The LEVEL is calibrated to ``target_share`` (which is measured on all
    donors, missing pay included), so dropping missing-pay donors from the
    gradient cannot bias the total.
    """
    observed = ~np.isnan(donor_annual_pay)
    cuts = np.percentile(donor_annual_pay[observed], [100 / 3, 200 / 3])
    bands = np.digitize(donor_annual_pay, cuts)  # 0 low / 1 mid / 2 high
    band_rates = np.array(
        [
            _weighted_mean(
                donor_was_neet[observed & (bands == b)],
                donor_weights[observed & (bands == b)],
            )
            for b in range(3)
        ]
    )
    receiver_bands = np.digitize(np.asarray(employment_income, dtype=float), cuts)
    prob = band_rates[receiver_bands]
    return _calibrate(prob, treated_mask, person_weights, target_share)


def _classifier_neet_probabilities(
    donor: pd.DataFrame,
    receiver: pd.DataFrame,
    target_share: float,
    treated_mask: np.ndarray,
    person_weights: np.ndarray,
) -> np.ndarray:
    """Classifier variant: P(entrant | age, gender, earnings), level calibrated.

    microcosm-fit's CategoricalClassifier gives every receiver a probability
    rather than a 0/1 label, so calibration can scale it to the target share.
    The fit takes the donor weights normalised to mean 1. The classifier's
    logit half normalises them that way itself, but its boosted half
    (scikit-learn's HistGradientBoostingClassifier) uses them as given: each
    leaf value divides a weighted gradient sum by a weighted hessian sum plus a
    fixed L2 penalty, so the penalty counts for less the larger the weights.
    Normalising makes the probabilities independent of the weights' scale.
    """
    from microcosm.fit import CategoricalClassifier

    weights = donor["weight"].to_numpy(dtype=float)
    model = CategoricalClassifier(categorical_predictors=("gender",), seed=CLASSIFIER_SEED).fit(
        donor, PREDICTORS, ["was_neet_recently"], weights=weights / weights.mean()
    )
    classes = model.classes_.tolist()
    if True not in classes:
        raise ValueError("The LFS donors hold no recent NEET entrants; nothing to impute.")
    prob = model.predict_proba(receiver[PREDICTORS])[:, classes.index(True)]
    return _calibrate(prob, treated_mask, person_weights, target_share)


def classifier_versions() -> dict[str, str | None]:
    """The packages behind the classifier, for the results JSON.

    Results published before the classifier recorded no microimpute version,
    which left the release behind them to inference. ``microcosm_fit_commit``
    comes from the install's PEP 610 record; it is None unless pip or uv
    installed microcosm-fit from git.
    """
    import importlib.metadata
    import json

    record = importlib.metadata.distribution("microcosm-fit").read_text("direct_url.json")
    commit = json.loads(record).get("vcs_info", {}).get("commit_id") if record else None
    return {
        "microcosm_fit": importlib.metadata.version("microcosm-fit"),
        "microcosm_fit_commit": commit,
        "scikit_learn": importlib.metadata.version("scikit-learn"),
    }


def build_neet_imputation(
    lfs_paths: list[str],
    baseline,
    year: int,
    treated_mask: np.ndarray,
    person_weights: np.ndarray,
) -> NeetImputation:
    """Impute P(was NEET within the past year) onto the baseline person axis."""
    treated_mask = np.asarray(treated_mask, dtype=bool)
    person_weights = np.asarray(person_weights, dtype=float)

    # Weeks-per-year from PolicyEngine (model constant), never hardcoded.
    from policyengine_uk.model_api import WEEKS_IN_YEAR

    lfs = load_panels(lfs_paths)
    panel = lfs[lfs.LGWT.notna()].copy()

    employed_w5, was_neet = neet_transition_targets(panel)
    age5 = panel.AGE5.to_numpy(dtype=float)
    weights = panel.LGWT.to_numpy(dtype=float)
    annual_pay = annualise_pay(panel.GRSSWK5.to_numpy(dtype=float), WEEKS_IN_YEAR)

    young_donors = employed_w5 & (age5 >= MARGINAL_AGE_LOWER) & (age5 <= REFORM_AGE_UPPER)
    entrant_share = _weighted_mean(was_neet[young_donors], weights[young_donors])

    model_donors = (
        employed_w5
        & (age5 >= LFS_ADULT_AGE_FLOOR)
        & (age5 < WORKING_AGE_CEILING)
        & ~np.isnan(annual_pay)
    )
    donor = pd.DataFrame(
        {
            "age": age5[model_donors],
            "gender": panel.SEX[model_donors].astype(int).map({1: "MALE", 2: "FEMALE"}).values,
            "employment_income": annual_pay[model_donors],
            "was_neet_recently": was_neet[model_donors],
            "weight": weights[model_donors],
        }
    )
    simulated = baseline.calculate_dataframe(PREDICTORS, year)
    # Plain columns, so the classifier sees values rather than a weighted frame.
    receiver = pd.DataFrame({column: np.asarray(simulated[column]) for column in PREDICTORS})

    probabilities = _classifier_neet_probabilities(
        donor, receiver, entrant_share, treated_mask, person_weights
    )
    banded_probabilities = banded_neet_probabilities(
        annual_pay[young_donors],
        was_neet[young_donors],
        weights[young_donors],
        entrant_share,
        receiver["employment_income"].to_numpy(dtype=float),
        treated_mask,
        person_weights,
    )

    panel_summary = {
        "count": len(lfs_paths),
        "period": derive_period(lfs_paths),
        "studies": derive_studies(lfs_paths),
        "total_respondents": int(len(lfs)),
        "employed_21_24_donors": int(young_donors.sum()),
        "neet_entrants_21_24": int(was_neet[young_donors].sum()),
        # The published results name these keys after the QRF; they keep the
        # names so the results schema doesn't change.
        "qrf_training_donors": int(model_donors.sum()),
        "qrf_training_positives": int(was_neet[model_donors].sum()),
    }
    return NeetImputation(
        probabilities=probabilities,
        banded_probabilities=banded_probabilities,
        entrant_share=entrant_share,
        panel_summary=panel_summary,
    )
