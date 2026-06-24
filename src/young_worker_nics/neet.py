"""NEET-history imputation from LFS five-quarter longitudinal panels.

Estimates each employed 21-24-year-old's probability of having been NEET
(non-employed and not enrolled as a student) at some point in the past year,
from LFS panel members observed NEET at any of waves 1-4 and employed at
wave 5. A QRF (microimpute) learns the shape of that probability over age,
gender and earnings; an earnings-banded estimator provides a sensitivity.
Both are calibrated so the FRS-weighted mean among treated employees equals
the directly measured, survey-weighted entrant share among employed 21-24
LFS donors: the level then rests on the LFS group rate, so dropping
missing-pay donors cannot bias it. Caveat: the stacked panels hold only a
few hundred employed 21-24 donors, so cell rates are noisy — the calibrated
level is more reliable than any single band. The QRF draw is seeded via
autoimpute's ``random_state`` (set to 0) for reproducibility.
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

QRF_RANDOM_STATE = 0

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


def _calibrate(
    prob: np.ndarray,
    treated_mask: np.ndarray,
    person_weights: np.ndarray,
    target_share: float,
) -> np.ndarray:
    """Scale so the weighted mean probability over treated people hits the target."""
    prob = np.where(treated_mask, prob, 0.0)
    uncalibrated = _weighted_mean(prob[treated_mask], person_weights[treated_mask])
    if uncalibrated <= 0:
        raise ValueError(
            "Imputed probabilities are zero across the treated population; "
            "cannot calibrate to the measured entrant share."
        )
    return np.clip(prob * (target_share / uncalibrated), 0.0, 1.0)


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


def _qrf_neet_probabilities(
    donor: pd.DataFrame,
    receiver: pd.DataFrame,
    target_share: float,
    treated_mask: np.ndarray,
    person_weights: np.ndarray,
) -> np.ndarray:
    """QRF (microimpute) variant: shape from age/gender/earnings, level calibrated."""
    from microimpute import QRF
    from microimpute.comparisons import autoimpute

    results = autoimpute(
        donor,
        receiver,
        predictors=["age", "gender", "employment_income"],
        imputed_variables=["was_neet_recently"],
        weight_col="weight",
        models=[QRF],
        random_state=QRF_RANDOM_STATE,
    )
    prob = results.receiver_data["was_neet_recently"].clip(0, 1).to_numpy()
    return _calibrate(prob, treated_mask, person_weights, target_share)


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

    qrf_donors = (
        employed_w5
        & (age5 >= LFS_ADULT_AGE_FLOOR)
        & (age5 < WORKING_AGE_CEILING)
        & ~np.isnan(annual_pay)
    )
    donor = pd.DataFrame(
        {
            "age": age5[qrf_donors],
            "gender": panel.SEX[qrf_donors].astype(int).map({1: "MALE", 2: "FEMALE"}).values,
            "employment_income": annual_pay[qrf_donors],
            "was_neet_recently": was_neet[qrf_donors].astype(float),
            "weight": weights[qrf_donors],
        }
    )
    receiver = baseline.calculate_dataframe(["age", "gender", "employment_income"], year)

    probabilities = _qrf_neet_probabilities(
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
        "qrf_training_donors": int(qrf_donors.sum()),
        "qrf_training_positives": int(was_neet[qrf_donors].sum()),
    }
    return NeetImputation(
        probabilities=probabilities,
        banded_probabilities=banded_probabilities,
        entrant_share=entrant_share,
        panel_summary=panel_summary,
    )
