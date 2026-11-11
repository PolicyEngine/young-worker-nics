"""Properties of ``_calibrate``, the step that sets the targeted population's level.

Invariants, for every input the function accepts:

1. Every output lies in [0, 1], and people outside the treated mask get 0.
2. The weighted mean over treated people equals the target whenever the
   target is reachable (at most the weighted share of treated people with a
   nonzero probability); otherwise the function raises.
3. One factor: every treated output is ``min(f * p, 1)`` for the same ``f``.
4. Order: a higher input probability never gets a lower output.
5. Rescaling every weight by one constant leaves the output unchanged.
6. Calibrating an already-calibrated vector returns it.
7. A higher target never lowers anyone's output.
8. Differential: where no scaled probability reaches 1, the output equals
   the published scale-then-clip formula bit for bit, so a run the clip
   never touched reproduces exactly.

Invariants 5-7 hold exactly in real arithmetic. In floats, when nearly all of
the target comes from people at the cap, the factor rests on the few below it,
and rounding can move a low-weight person's output by more than one ulp. So
those tests bound the weighted mean difference over treated people, the
quantity every published figure sums.

The generated probabilities and targets are 0, 1 or at least 1e-12, and the
weights 0 or at least 1e-6, so no product or weighted mean underflows; real
inputs sit far from that range. ``test_a_tiny_probability_does_not_stall_the_search``
covers an extreme bracket by hand.
"""

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from young_worker_nics.neet import _calibrate, _weighted_mean

SHARE_TOLERANCE = 1e-9
WEIGHTED_TOLERANCE = 1e-9


probabilities = st.one_of(st.sampled_from([0.0, 1.0]), st.floats(1e-12, 1))
shares = st.one_of(st.just(0.0), st.floats(1e-12, 1))
person_weights = st.one_of(st.just(0.0), st.floats(1e-6, 1e4))


@st.composite
def calibration_inputs(draw):
    n = draw(st.integers(1, 40))
    prob = np.array(draw(st.lists(probabilities, min_size=n, max_size=n)))
    weights = np.array(draw(st.lists(person_weights, min_size=n, max_size=n)))
    treated = np.array(draw(st.lists(st.booleans(), min_size=n, max_size=n)))
    assume(weights[treated].sum() > 0)
    assume((prob[treated] * weights[treated]).sum() > 0)
    target = draw(shares)
    return prob, treated, weights, target


def reachable_share(prob, treated, weights):
    w = weights[treated]
    return float((w * (prob[treated] > 0)).sum() / w.sum())


def weighted_share(values, treated, weights):
    w = weights[treated]
    return float((w * values[treated]).sum() / w.sum())


def weighted_gap(a, b, treated, weights):
    """Weighted mean of |a - b| over treated people."""
    w = weights[treated]
    return float((w * np.abs(a - b)[treated]).sum() / w.sum())


def published_formula(prob, treated, weights, target):
    """Step 8's calibration as published (30f5b65), copied verbatim."""
    prob = np.where(treated, prob, 0.0)
    uncalibrated = _weighted_mean(prob[treated], weights[treated])
    return np.clip(prob * (target / uncalibrated), 0.0, 1.0)


def calibrate_or_none(prob, treated, weights, target):
    if target > reachable_share(prob, treated, weights) + 1e-12:
        with pytest.raises(ValueError, match="No scaling"):
            _calibrate(prob, treated, weights, target)
        return None
    return _calibrate(prob, treated, weights, target)


@settings(max_examples=400, deadline=None)
@given(calibration_inputs())
def test_bounds_mask_and_target(inputs):
    prob, treated, weights, target = inputs
    out = calibrate_or_none(prob, treated, weights, target)
    if out is None:
        return
    assert ((out >= 0) & (out <= 1)).all()
    assert (out[~treated] == 0).all()
    assert abs(weighted_share(out, treated, weights) - target) <= SHARE_TOLERANCE


@settings(max_examples=400, deadline=None)
@given(calibration_inputs())
def test_one_factor_and_order(inputs):
    prob, treated, weights, target = inputs
    out = calibrate_or_none(prob, treated, weights, target)
    if out is None:
        return
    p, o = prob[treated], out[treated]
    assert (o[p == 0] == 0).all()
    below_one = (p > 0) & (o < 1)
    if below_one.any():
        factors = o[below_one] / p[below_one]
        assert np.allclose(factors, factors[0], rtol=1e-12, atol=0)
        # Anyone at 1 has a scaled probability of at least 1.
        assert (p[o >= 1] * factors[0] >= 1 - 1e-12).all()
    order = np.argsort(p, kind="stable")
    assert (np.diff(o[order]) >= -1e-15).all()


@settings(max_examples=300, deadline=None)
@given(calibration_inputs(), st.floats(1e-3, 1e3))
def test_weight_scale_invariance(inputs, scale):
    prob, treated, weights, target = inputs
    out = calibrate_or_none(prob, treated, weights, target)
    if out is None:
        return
    rescaled = _calibrate(prob, treated, weights * scale, target)
    assert weighted_gap(rescaled, out, treated, weights) <= WEIGHTED_TOLERANCE


@settings(max_examples=300, deadline=None)
@given(calibration_inputs())
def test_idempotent(inputs):
    prob, treated, weights, target = inputs
    out = calibrate_or_none(prob, treated, weights, target)
    if out is None or weighted_share(out, treated, weights) <= 0:
        return
    again = _calibrate(out, treated, weights, target)
    assert weighted_gap(again, out, treated, weights) <= WEIGHTED_TOLERANCE


@settings(max_examples=300, deadline=None)
@given(calibration_inputs(), shares)
def test_monotone_in_target(inputs, other_target):
    prob, treated, weights, target = inputs
    low, high = sorted([target, other_target])
    if high > reachable_share(prob, treated, weights):
        return
    out_low = _calibrate(prob, treated, weights, low)
    out_high = _calibrate(prob, treated, weights, high)
    shortfall = np.maximum(out_low - out_high, 0.0)
    assert weighted_gap(shortfall, np.zeros_like(shortfall), treated, weights) <= WEIGHTED_TOLERANCE


@settings(max_examples=400, deadline=None)
@given(calibration_inputs())
def test_matches_published_formula_where_the_clip_never_binds(inputs):
    prob, treated, weights, target = inputs
    p = prob[treated]
    factor = target / _weighted_mean(p, weights[treated])
    assume(factor * p.max() <= 1)
    published = published_formula(prob, treated, weights, target)
    assert np.array_equal(_calibrate(prob, treated, weights, target), published)


# ── Examples ─────────────────────────────────────────────────────────────────


def test_labels_below_the_target_cannot_be_calibrated():
    """The published failure: 0/1 labels whose share sits below the target."""
    labels = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
    treated = np.ones(5, dtype=bool)
    weights = np.ones(5)
    # Scale-then-clip leaves the share at 0.2, short of the 0.25 target.
    assert np.average(published_formula(labels, treated, weights, 0.25)) == pytest.approx(0.2)
    with pytest.raises(ValueError, match="No scaling"):
        _calibrate(labels, treated, weights, 0.25)


def test_clipped_mass_moves_to_people_below_one():
    prob = np.array([0.9, 0.3, 0.1, 0.0])
    treated = np.ones(4, dtype=bool)
    weights = np.ones(4)
    out = _calibrate(prob, treated, weights, 0.5)
    # Scaling by 0.5 / 0.325 would put the first person above 1; the factor
    # that puts the mean at 0.5 caps them at 1 and gives the rest 2.5x.
    assert out == pytest.approx([1.0, 0.75, 0.25, 0.0])
    assert out.mean() == pytest.approx(0.5)


def test_downward_calibration_matches_scaling():
    prob = np.array([0.8, 0.4, 0.2])
    treated = np.ones(3, dtype=bool)
    weights = np.array([1.0, 2.0, 1.0])
    out = _calibrate(prob, treated, weights, 0.1)
    assert out == pytest.approx(prob * 0.1 / np.average(prob, weights=weights))


@pytest.mark.parametrize(
    ("prob", "weights", "target", "message"),
    [
        ([0.0, 0.0], [1.0, 1.0], 0.1, "zero across"),
        ([0.5, 1.5], [1.0, 1.0], 0.1, r"\[0, 1\]"),
        ([0.5, np.nan], [1.0, 1.0], 0.1, r"\[0, 1\]"),
        ([0.5, 0.5], [1.0, -1.0], 0.1, "weights"),
        ([0.5, 0.5], [0.0, 0.0], 0.1, "weights"),
        ([0.5, 0.5], [1.0, 1.0], 1.5, "target share"),
    ],
)
def test_refuses_invalid_input(prob, weights, target, message):
    with pytest.raises(ValueError, match=message):
        _calibrate(np.array(prob), np.ones(2, dtype=bool), np.array(weights), target)


def test_a_tiny_probability_does_not_stall_the_search():
    """The factor's bracket can span hundreds of orders of magnitude."""
    prob = np.array([0.9, 0.3, 1e-300, 0.0])
    treated = np.ones(4, dtype=bool)
    weights = np.ones(4)
    out = _calibrate(prob, treated, weights, 0.5)
    assert out.mean() == pytest.approx(0.5, abs=1e-12)
    assert out[:2] == pytest.approx([1.0, 1.0])
    # The factor is 1 / 0.3, so the tiny probability scales by that and no more.
    assert out[2] / prob[2] == pytest.approx(1 / 0.3, rel=1e-9)
