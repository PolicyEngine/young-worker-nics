"""Young-worker employer NICs exemption analysis.

Models extending the employer NICs zero rate (currently under-21s and
apprentices under 25) to all employees aged 18-24, using the PolicyEngine UK
microsimulation model.
"""

from .formulas import employment_cost_reduction_pct, exempt_employer_nics
from .pipeline import run

__all__ = [
    "employment_cost_reduction_pct",
    "exempt_employer_nics",
    "run",
]
