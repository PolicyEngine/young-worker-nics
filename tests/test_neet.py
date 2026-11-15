"""Unit tests for the NEET imputation logic (pure pandas/numpy, no microdata).

The transition-target, sentinel, banded-estimator, classifier and
panel-loading logic are all testable on synthetic data. The classifier tests
need Microcosm (the ``lfs`` extra) and skip without it; the full Step 8 path
also needs a PolicyEngine baseline and the LFS panels, so no test runs it.
"""

import numpy as np
import pandas as pd
import pytest

from young_worker_nics.neet import (
    _classifier_neet_probabilities,
    annualise_pay,
    banded_neet_probabilities,
    classifier_versions,
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
    annual = annualise_pay(np.array([-8.0, -9.0, 0.0, 100.0]), 52)
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


# ── Classifier ───────────────────────────────────────────────────────────────


def classifier_case(seed: int = 0, n_donor: int = 800, n_receiver: int = 400):
    """Synthetic donors with a known age and pay gradient, and receivers to score."""
    rng = np.random.default_rng(seed)
    age = rng.integers(16, 65, n_donor).astype(float)
    pay = rng.lognormal(10, 0.5, n_donor)
    logit = -2.0 - 0.08 * (age - 30) - 0.5 * (np.log(pay) - 10)
    donor = pd.DataFrame(
        {
            "age": age,
            "gender": rng.choice(["MALE", "FEMALE"], n_donor),
            "employment_income": pay,
            "was_neet_recently": rng.random(n_donor) < 1 / (1 + np.exp(-logit)),
            "weight": rng.lognormal(np.log(300), 0.4, n_donor),
        }
    )
    receiver = pd.DataFrame(
        {
            "age": rng.integers(16, 30, n_receiver).astype(float),
            "gender": rng.choice(["MALE", "FEMALE"], n_receiver),
            "employment_income": rng.lognormal(10, 0.5, n_receiver),
        }
    )
    treated = ((receiver["age"] >= 21) & (receiver["age"] <= 24)).to_numpy()
    weights = rng.lognormal(np.log(500), 0.3, n_receiver)
    return donor, receiver, treated, weights


def test_classifier_gives_probabilities_that_hit_the_target():
    pytest.importorskip("microcosm.fit")
    donor, receiver, treated, weights = classifier_case()
    prob = _classifier_neet_probabilities(donor, receiver, 0.2, treated, weights)
    assert (prob[~treated] == 0).all()
    assert ((prob >= 0) & (prob <= 1)).all()
    # Probabilities, not the 0/1 labels behind the published shortfall.
    assert len(np.unique(prob[treated])) > 10
    assert np.average(prob[treated], weights=weights[treated]) == pytest.approx(0.2, abs=1e-9)


def test_classifier_ignores_the_scale_of_donor_weights():
    pytest.importorskip("microcosm.fit")
    donor, receiver, treated, weights = classifier_case()
    base = _classifier_neet_probabilities(donor, receiver, 0.2, treated, weights)
    scaled = donor.assign(weight=donor["weight"] * 1000)
    rescaled = _classifier_neet_probabilities(scaled, receiver, 0.2, treated, weights)
    assert np.allclose(rescaled, base, rtol=1e-9, atol=1e-12)


def test_classifier_repeats_its_probabilities():
    pytest.importorskip("microcosm.fit")
    donor, receiver, treated, weights = classifier_case()
    first = _classifier_neet_probabilities(donor, receiver, 0.2, treated, weights)
    second = _classifier_neet_probabilities(donor, receiver, 0.2, treated, weights)
    assert np.array_equal(first, second)


def test_classifier_refuses_donors_without_entrants():
    pytest.importorskip("microcosm.fit")
    donor, receiver, treated, weights = classifier_case()
    with pytest.raises(ValueError, match="no recent NEET entrants"):
        _classifier_neet_probabilities(
            donor.assign(was_neet_recently=False), receiver, 0.2, treated, weights
        )


def test_classifier_refuses_gender_codes_the_donors_lack():
    """A receiver coded "Male" against donors coded "MALE" fails loudly."""
    pytest.importorskip("microcosm.fit")
    donor, receiver, treated, weights = classifier_case()
    with pytest.raises(ValueError, match="never saw"):
        _classifier_neet_probabilities(donor, receiver.assign(gender="Male"), 0.2, treated, weights)


def test_classifier_versions_name_the_installed_packages():
    """The results record what ran, so a rerun needn't infer it."""
    pytest.importorskip("microcosm.fit")
    versions = classifier_versions()
    assert versions["microcosm_fit"] and versions["scikit_learn"]
    commit = versions["microcosm_fit_commit"]
    assert commit is None or (len(commit) == 40 and set(commit) <= set("0123456789abcdef"))


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


def test_derive_studies_falls_back_to_panel_names_on_unparseable_path():
    assert derive_studies(["/data/panel_a.tab"]) == (
        "UK Data Service LFS five-quarter longitudinal panels (panel_a)"
    )
