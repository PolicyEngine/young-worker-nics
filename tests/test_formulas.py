"""Unit tests for the pure-Python statutory arithmetic (no PolicyEngine needed)."""

import numpy as np
import pytest

from young_worker_nics.formulas import employment_cost_reduction_pct, exempt_employer_nics

# 2026-27 parameters
ST = 5_000.0
UST = 50_270.0
RATE = 0.15


def test_below_secondary_threshold_saves_nothing():
    assert exempt_employer_nics(np.array([0.0, 4_000.0, 5_000.0]), ST, UST, RATE).tolist() == [
        0.0,
        0.0,
        0.0,
    ]


def test_typical_young_worker():
    # £25,000: relief on £20,000 at 15% = £3,000
    saving = exempt_employer_nics(np.array([25_000.0]), ST, UST, RATE)
    assert np.isclose(saving[0], 3_000.0)


def test_relief_capped_at_upper_secondary_threshold():
    # Above the UST the relieved band stops growing: (50,270 - 5,000) × 15%
    saving = exempt_employer_nics(np.array([60_000.0, 100_000.0]), ST, UST, RATE)
    expected = (UST - ST) * RATE
    assert np.allclose(saving, expected)


def test_cost_wedge_for_typical_worker():
    # £25,000: saving £3,000 over total cost £28,000 ≈ 10.7%
    wedge = employment_cost_reduction_pct(np.array([25_000.0]), ST, UST, RATE)
    assert np.isclose(wedge[0], 3_000.0 / 28_000.0)


def test_nonpositive_earnings_raise():
    with pytest.raises(ValueError, match="positive earnings"):
        employment_cost_reduction_pct(np.array([0.0]), ST, UST, RATE)


def test_formulas_preserve_pandas_weights():
    # Binary ufuncs must dispatch through pandas so MicroSeries weights
    # survive; a plain Series stands in for MicroSeries here.
    import pandas as pd

    earnings = pd.Series([25_000.0, 60_000.0])
    saving = exempt_employer_nics(earnings, ST, UST, RATE)
    assert isinstance(saving, pd.Series)
