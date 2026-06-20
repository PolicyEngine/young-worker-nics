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
        "--dataset",
        default=None,
        help=(
            "Path to an enhanced-FRS .h5 to simulate on directly (bypassing "
            "the policyengine bundle). Required for the public/private employer "
            "split, which needs the employment_sector variable (policyengine-uk "
            ">=2.89.2 and an enhanced FRS built from policyengine-uk-data "
            ">=1.56.5). When omitted, the managed bundle simulation is used and "
            "the public-sector split is skipped."
        ),
    )
    parser.add_argument(
        "--populace",
        action="store_true",
        help=(
            "Build BOTH baseline and reform simulations through the "
            "policyengine.py wrapper on the Populace UK dataset (via "
            "managed_microsimulation with allow_unmanaged=True), instead of "
            "the enhanced-FRS direct path. Provides employment_sector, so the "
            "public/private employer split is produced. Mutually exclusive "
            "with --dataset."
        ),
    )
    parser.add_argument(
        "--populace-year",
        type=int,
        default=2023,
        help="Populace UK dataset vintage to load when --populace is set (default 2023).",
    )
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
        "--lfs-path",
        nargs="+",
        default=None,
        help=(
            "One or more LFS 5-quarter longitudinal panel .tab files "
            "(e.g. ~/Downloads/UKDA-*-tab/tab/*.tab). When given, the pipeline "
            "also builds the targeted-population results (employed 21-24s who "
            "were NEET within the past year); otherwise the JSON's 'targeted' "
            "section is null."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.populace and args.dataset:
        raise SystemExit("--populace and --dataset are mutually exclusive.")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
