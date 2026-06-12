"""Unit tests for the NEET imputation logic (pure pandas/numpy, no microdata).

The QRF path needs microimpute and a PolicyEngine baseline, so it is not
exercised here; the transition-target, sentinel, banded-estimator and
panel-loading logic are all testable on synthetic data.
"""

import numpy as np
import pandas as pd
import pytest

from young_worker_nics.neet import (
    annualise_pay,
    banded_neet_probabilities,
    derive_period,
    derive_studies,
    load_panels,
    neet_transition_targets,
)


def make_panel(rows: list[dict]) -> pd.DataFrame:
    """Build a synthetic 5-wave panel from {'inc': [...5], 'enr': [...5], ...} rows."""
    data = {}
    for q in range(1, 6):
        data[f"INCAC05{q}"] = [r["inc"][q - 1] for r in rows]
        data[f"ENROLL{q}"] = [r["enr"][q - 1] for r in rows]
    data["AGE5"] = [r.get("age", 22) for r in rows]
    data["SEX"] = [r.get("sex", 1) for r in rows]
    data["GRSSWK5"] = [r.get("pay", 300.0) for r in rows]
    data["LGWT"] = [r.get("wt", 1.0) for r in rows]
    return pd.DataFrame(data)


# ── Transition target ────────────────────────────────────────────────────────


def test_neet_then_employed_is_an_entrant():
    panel = make_panel([{"inc": [6, 6, 1, 1, 1], "enr": [2, 2, 2, 2, 2]}])
    employed_w5, was_neet = neet_transition_targets(panel)
    assert was_neet.tolist() == [True]
    assert employed_w5.tolist() == [True]


def test_enrolled_student_is_not_neet():
    # Non-employed at waves 1-2 but enrolled (ENROLL == 1): excluded from NEET.
    panel = make_panel([{"inc": [6, 6, 1, 1, 1], "enr": [1, 1, 2, 2, 2]}])
    _, was_neet = neet_transition_targets(panel)
    assert was_neet.tolist() == [False]


def test_partially_enrolled_neet_spell_still_counts():
    # Enrolled during wave 1 but NEET at wave 2: the wave-2 spell counts.
    panel = make_panel([{"inc": [6, 6, 1, 1, 1], "enr": [1, 2, 2, 2, 2]}])
    _, was_neet = neet_transition_targets(panel)
    assert was_neet.tolist() == [True]


def test_continuously_employed_is_not_neet():
    panel = make_panel([{"inc": [1, 2, 3, 4, 1], "enr": [2, 2, 2, 2, 2]}])
    employed_w5, was_neet = neet_transition_targets(panel)
    assert was_neet.tolist() == [False]
    assert employed_w5.tolist() == [True]


def test_employed_at_wave_5_requires_incac_1_to_4():
    panel = make_panel(
        [
            {"inc": [6, 1, 1, 1, 4], "enr": [2] * 5},  # 4 = still employed
            {"inc": [6, 1, 1, 1, 5], "enr": [2] * 5},  # 5 = not employed at wave 5
            {"inc": [6, 1, 1, 1, 0], "enr": [2] * 5},  # below the employed range
        ]
    )
    employed_w5, was_neet = neet_transition_targets(panel)
    assert employed_w5.tolist() == [True, False, False]
    assert was_neet.tolist() == [True, True, True]


def test_neet_only_at_wave_5_does_not_count():
    # The lookback is waves 1-4 only.
    panel = make_panel([{"inc": [1, 1, 1, 1, 6], "enr": [2] * 5}])
    employed_w5, was_neet = neet_transition_targets(panel)
    assert was_neet.tolist() == [False]
    assert employed_w5.tolist() == [False]


# ── Pay sentinels ────────────────────────────────────────────────────────────


def test_negative_pay_sentinels_are_missing_not_zero():
    annual = annualise_pay(np.array([-8.0, -9.0, 0.0, 100.0]))
    assert np.isnan(annual[0]) and np.isnan(annual[1])
    assert annual[2] == 0.0
    assert annual[3] == 5_200.0


# ── Banded estimator + calibration ───────────────────────────────────────────


def test_banded_estimator_gradient_and_calibration():
    # Three donors per pay tercile; entrant rates 2/3 (low), 1/3 (mid), 0 (high).
    donor_pay = np.array([1_000, 1_100, 1_200, 5_000, 5_100, 5_200, 9_000, 9_100, 9_200], float)
    donor_neet = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0], float)
    donor_w = np.ones(9)
    target = 0.2

    income = np.array([2_000.0, 5_050.0, 9_500.0, 5_050.0])
    treated = np.array([True, True, True, False])
    weights = np.ones(4)

    prob = banded_neet_probabilities(
        donor_pay, donor_neet, donor_w, target, income, treated, weights
    )

    # Zero outside the treated mask, all probabilities valid.
    assert prob[3] == 0.0
    assert np.all((prob >= 0) & (prob <= 1))
    # Earnings gradient preserved: low band > mid band > high band.
    assert prob[0] > prob[1] > prob[2]
    # Raw band rates are 2/3, 1/3, 0; calibration rescales the level.
    assert np.isclose(prob[0] / prob[1], 2.0)
    assert prob[2] == 0.0
    # Calibrated: weighted mean over treated equals the target share.
    assert np.isclose(np.average(prob[treated], weights=weights[treated]), target)


def test_banded_estimator_ignores_missing_pay_donors():
    donor_pay = np.array([1_000, 1_100, 1_200, 5_000, 5_100, 5_200, 9_000, 9_100, 9_200], float)
    donor_neet = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0], float)
    donor_w = np.ones(9)
    income = np.array([2_000.0, 5_050.0, 9_500.0])
    treated = np.ones(3, dtype=bool)
    weights = np.ones(3)

    base = banded_neet_probabilities(donor_pay, donor_neet, donor_w, 0.2, income, treated, weights)
    # A heavily weighted missing-pay positive must not move the gradient.
    with_missing = banded_neet_probabilities(
        np.append(donor_pay, np.nan),
        np.append(donor_neet, 1.0),
        np.append(donor_w, 1_000.0),
        0.2,
        income,
        treated,
        weights,
    )
    assert np.allclose(base, with_missing)


def test_banded_estimator_calibration_respects_person_weights():
    donor_pay = np.array([1_000, 1_100, 1_200, 5_000, 5_100, 5_200, 9_000, 9_100, 9_200], float)
    donor_neet = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0], float)
    donor_w = np.ones(9)
    target = 0.15

    income = np.array([2_000.0, 9_500.0])
    treated = np.array([True, True])
    weights = np.array([3.0, 1.0])

    prob = banded_neet_probabilities(
        donor_pay, donor_neet, donor_w, target, income, treated, weights
    )
    assert np.isclose(np.average(prob, weights=weights), target)


# ── load_panels weight detection ─────────────────────────────────────────────


def write_tab(path, columns, rows):
    lines = ["\t".join(columns)] + ["\t".join(str(v) for v in row) for row in rows]
    path.write_text("\n".join(lines) + "\n")


def test_load_panels_detects_and_renames_vintage_weights(tmp_path):
    f1 = tmp_path / "lgwt22_5q_aj22_aj23_eul.tab"
    f2 = tmp_path / "lgwt24_5q_od23_od24_eul.tab"
    write_tab(f1, ["AGE5", "LGWT22"], [[22, 1.5], [23, 2.0]])
    write_tab(f2, ["AGE5", "LGWT24"], [[24, 0.5]])

    panel = load_panels([str(f1), str(f2)])
    assert len(panel) == 3
    assert "LGWT" in panel.columns
    assert "LGWT22" not in panel.columns and "LGWT24" not in panel.columns
    assert panel["LGWT"].tolist() == [1.5, 2.0, 0.5]


def test_load_panels_rejects_ambiguous_or_missing_weights(tmp_path):
    no_weight = tmp_path / "no_weight.tab"
    write_tab(no_weight, ["AGE5", "WEIGHT"], [[22, 1.0]])
    with pytest.raises(ValueError, match="LGWT"):
        load_panels([str(no_weight)])

    two_weights = tmp_path / "two_weights.tab"
    write_tab(two_weights, ["AGE5", "LGWT22", "LGWT23"], [[22, 1.0, 2.0]])
    with pytest.raises(ValueError, match="LGWT"):
        load_panels([str(two_weights)])


# ── panel_summary helpers ────────────────────────────────────────────────────


def test_derive_period_and_studies_from_real_style_paths():
    paths = [
        "/data/UKDA-9133-tab/tab/lgwt22_5q_aj22_aj23_eul.tab",
        "/data/UKDA-9487-tab/tab/lgwt24_5q_od23_od24_eul.tab",
    ]
    assert derive_period(paths) == "Apr-Jun 2022 to Oct-Dec 2024"
    assert derive_studies(paths) == "UKDA SN 9133, 9487"


def test_derive_period_raises_on_unparseable_filename():
    with pytest.raises(ValueError, match="Cannot parse the panel period"):
        derive_period(["/data/panel_a.tab", "/data/panel_b.tab"])


def test_derive_studies_raises_on_unparseable_path():
    with pytest.raises(ValueError, match="Cannot parse the UKDA study number"):
        derive_studies(["/data/panel_a.tab"])
