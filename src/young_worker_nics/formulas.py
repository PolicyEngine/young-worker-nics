"""Statutory NICs arithmetic, shared by the pipeline, calculator, and tests.

Weight-preserving: pandas-like inputs (including microdf's MicroSeries) are
clipped via their own ``.clip`` method, which propagates weights; plain
ndarrays go through ``np.clip``. Never coerce inputs with ``np.asarray``
here — that would strip MicroSeries weights, and the pipeline asserts they
survive.
"""

from __future__ import annotations

import numpy as np


def _clip(values, lower=None, upper=None):
    if isinstance(values, np.ndarray):
        return np.clip(values, lower, upper)
    return values.clip(lower=lower, upper=upper)


def exempt_employer_nics(
    earnings,
    secondary_threshold: float,
    upper_secondary_threshold: float,
    employer_rate: float,
):
    """Employer NICs forgone per person under a zero-rate up to the UST.

    Mirrors the structure of the existing under-21 (category M) and
    apprentice-under-25 (category H) reliefs: the zero rate applies between
    the Secondary Threshold and the Upper Secondary Threshold only; employer
    NICs remain due at the full rate above the UST.
    """
    relieved_band = _clip(earnings, upper=upper_secondary_threshold) - secondary_threshold
    return _clip(relieved_band, lower=0.0) * employer_rate


def employment_cost_reduction_pct(
    earnings,
    secondary_threshold: float,
    upper_secondary_threshold: float,
    employer_rate: float,
):
    """Percentage fall in total employment cost (gross pay + employer NICs).

    The wedge change drives the labour demand response. Requires positive
    earnings — restrict to employees before calling.
    """
    if np.any(np.asarray(earnings) <= 0):
        raise ValueError(
            "employment_cost_reduction_pct requires positive earnings; filter to employees first."
        )
    saving = exempt_employer_nics(
        earnings, secondary_threshold, upper_secondary_threshold, employer_rate
    )
    full_nics = _clip(earnings - secondary_threshold, lower=0.0) * employer_rate
    return saving / (earnings + full_nics)
