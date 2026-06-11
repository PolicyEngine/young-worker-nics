"""Young-worker employer NICs exemption analysis.

Models extending the employer NICs zero rate (currently under-21s and
apprentices under 25) to all employees aged 18-24, using the PolicyEngine UK
microsimulation model.
"""

from .formulas import employment_cost_reduction_pct, exempt_employer_nics

__all__ = [
    "employment_cost_reduction_pct",
    "exempt_employer_nics",
    "run",
]


def __getattr__(name: str):
    # `run` pulls in the PolicyEngine stack, which only the [simulation]
    # extra installs; import it lazily so the statutory-arithmetic tests
    # run without it.
    if name == "run":
        from .pipeline import run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
