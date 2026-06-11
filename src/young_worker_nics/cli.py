"""Command-line entry point for the young-worker NICs exemption pipeline.

Exposes a :func:`main` callable that ``[project.scripts]`` registers as
``young-worker-nics-build`` and that ``__main__.py`` invokes for
``python -m young_worker_nics``.

All defaults come from :mod:`young_worker_nics.sources`, where each value
carries a description and a source URL.
"""

from __future__ import annotations

import argparse

from .pipeline import run
from .sources import (
    CALCULATOR_ANNUAL_RENT,
    DEMAND_ELASTICITIES,
    PASS_THROUGH_SCENARIOS,
)


def _nonzero_elasticity(raw: str) -> float:
    value = float(raw)
    if value == 0:
        raise argparse.ArgumentTypeError("demand elasticities must be nonzero")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="young-worker-nics-build",
        description="Generate dashboard-ready young-worker NICs exemption results.",
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--pass-through",
        type=float,
        nargs="+",
        default=[s.value for s in PASS_THROUGH_SCENARIOS],
        help="Wage pass-through scenarios; see sources.PASS_THROUGH_SCENARIOS for citations.",
    )
    parser.add_argument(
        "--demand-elasticity-low",
        type=_nonzero_elasticity,
        default=DEMAND_ELASTICITIES["low"].value,
        help=DEMAND_ELASTICITIES["low"].description,
    )
    parser.add_argument(
        "--demand-elasticity-central",
        type=_nonzero_elasticity,
        default=DEMAND_ELASTICITIES["central"].value,
        help=DEMAND_ELASTICITIES["central"].description,
    )
    parser.add_argument(
        "--demand-elasticity-high",
        type=_nonzero_elasticity,
        default=DEMAND_ELASTICITIES["high"].value,
        help=DEMAND_ELASTICITIES["high"].description,
    )
    parser.add_argument(
        "--include-calculator",
        action="store_true",
        help=(
            "Also build the single-worker household calculator (slow: one "
            "PolicyEngine household call per grid point per profile). The "
            "dashboard shows the Household view only when this data exists."
        ),
    )
    parser.add_argument(
        "--calculator-rent",
        type=float,
        default=CALCULATOR_ANNUAL_RENT.value,
        help=CALCULATOR_ANNUAL_RENT.description,
    )
    parser.add_argument("--grid-min", type=float, default=4_000)
    parser.add_argument("--grid-max", type=float, default=60_000)
    parser.add_argument("--grid-count", type=int, default=29)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
