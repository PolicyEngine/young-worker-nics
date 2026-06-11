"""Single registry of every non-PolicyEngine number used in the analysis.

Policy: statutory parameters come from the PolicyEngine parameter tree at run
time and are never written here. Everything else — empirical assumptions and
official statistics used as anchors or context — lives in this module with a
value, a description, and a source URL, and is emitted verbatim into the
results JSON so the dashboard renders no hardcoded numbers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# ── Reform definition ────────────────────────────────────────────────────────
# Under-21s (category M) are already zero-rated, so the marginal population is
# 21-24-year-olds. (Apprentices under 25 are also exempt in law but are
# unobserved in the FRS and not modelled.)
REFORM_AGE_LOWER = 18
REFORM_AGE_UPPER = 24  # inclusive
MARGINAL_AGE_LOWER = 21

WEEKS_PER_YEAR = 52  # PolicyEngine stores NICs thresholds per week


@dataclass(frozen=True)
class Source:
    value: Any
    description: str
    url: str


# ── Empirical assumptions (CLI defaults) ─────────────────────────────────────

PASS_THROUGH_SCENARIOS = [
    Source(
        value=0.0,
        description=(
            "Central case: zero pass-through to targeted workers' own wages, "
            "from the Swedish under-26 payroll tax cut (Saez, Schoefer & Seim "
            "2019 AER)."
        ),
        url="https://www.aeaweb.org/articles?id=10.1257/aer.20171937",
    ),
    Source(
        value=0.25,
        description=(
            "Intermediate sensitivity, in the range found for regional payroll "
            "tax changes (Bennmarker et al. 2009; Korkeamäki & Uusitalo 2009)."
        ),
        url="https://doi.org/10.1016/j.labeco.2009.04.003",
    ),
    Source(
        value=0.60,
        description=(
            "OBR first-year assumption for the 2024 employer NICs rise, "
            "applied symmetrically (EFO October 2024)."
        ),
        url="https://obr.uk/efo/economic-and-fiscal-outlook-october-2024/",
    ),
    Source(
        value=0.76,
        description=(
            "OBR medium-term assumption for the 2024 employer NICs rise, "
            "applied symmetrically (EFO October 2024)."
        ),
        url="https://obr.uk/efo/economic-and-fiscal-outlook-october-2024/",
    ),
]

DEMAND_ELASTICITIES = {
    "low": Source(
        value=-0.15,
        description="Lower bound of Hamermesh's (1993) constant-output range.",
        url="https://press.princeton.edu/books/paperback/9780691025872/labor-demand",
    ),
    "central": Source(
        value=-0.31,
        description=(
            "Youth labour demand elasticity from the Swedish payroll tax cut "
            "(Egebark & Kaunitz 2018, Labour Economics)."
        ),
        url="https://doi.org/10.1016/j.labeco.2018.10.001",
    ),
    "high": Source(
        value=-0.50,
        description=(
            "Upper sensitivity, within the low-skilled range of the Lichter, "
            "Peichl & Siegloch (2015) meta-analysis (median -0.25)."
        ),
        url="https://doi.org/10.1016/j.euroecorev.2015.08.007",
    ),
}

CALCULATOR_ANNUAL_RENT = Source(
    value=9_600,
    description=(
        "Illustrative private rent for the renter calculator profile "
        "(£800/month, around the level of a modest one-bed/room outside "
        "London)."
    ),
    url="https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/privaterentandhousepricesuk/latest",
)

# ── Statutory facts PolicyEngine UK does not model ───────────────────────────

EMPLOYMENT_ALLOWANCE = Source(
    value=10_500,
    description=(
        "Employment Allowance: annual employer NICs relief for eligible "
        "employers from April 2025; not modelled in PolicyEngine UK (no "
        "employer-level data in the FRS)."
    ),
    url="https://www.gov.uk/claim-employment-allowance",
)

EXISTING_RELIEFS = {
    "under_21_relief": Source(
        value=None,
        description="Zero rate of employer NICs for under-21s (category M), since April 2015.",
        url="https://www.gov.uk/national-insurance-rates-letters",
    ),
    "apprentice_relief": Source(
        value=None,
        description=(
            "Zero rate of employer NICs for apprentices under 25 (category H), since April 2016."
        ),
        url="https://www.gov.uk/national-insurance-rates-letters",
    ),
    "rates_and_thresholds": Source(
        value=None,
        description="HMRC rates and thresholds for employers, 2026-27.",
        url="https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027",
    ),
    "nics_act_2025": Source(
        value=None,
        description=(
            "National Insurance Contributions (Secondary Class 1 "
            "Contributions) Act 2025: 15% rate and £5,000 Secondary Threshold "
            "from April 2025."
        ),
        url="https://www.legislation.gov.uk/ukpga/2025/11",
    ),
}

# ── Official statistics used as context and validation anchors ───────────────

OFFICIAL_STATS = {
    "neet": {
        "level": 1_012_000,
        "rate": 0.135,
        "year_on_year_change": 89_000,
        "period_label": "Jan-Mar 2026",
        "change_period_label": "January-March 2025 to January-March 2026",
        "release_label": "ONS, May 2026",
        "description": "Young people aged 16-24 not in education, employment or training, UK.",
        "source": "https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment/bulletins/youngpeoplenotineducationemploymentortrainingneet/may2026",
    },
    "hmrc_relief": {
        "under_21_relief_cost_2024_25_bn": 1.1,
        "under_21_relief_forecast_2025_26_bn": 1.9,
        "apprentice_relief_forecast_2025_26_bn": 0.57,
        "under_21_employers_claiming_2024_25": 340_000,
        "outturn_period_label": "2024-25",
        "forecast_period_label": "2025-26",
        "description": (
            "HMRC tax relief statistics (January 2026), Table 2: measured cost "
            "of the under-21 (category M) and apprentice under-25 (category H) "
            "employer NICs zero rates. The 2025-26 forecast is the first scored "
            "at post-April-2025 parameters (15% rate, £5,000 Secondary "
            "Threshold), so it is directly comparable with the model's "
            "relieved band. HMRC measures relief actually claimed through "
            "payroll category letters, which undercounts entitlement where "
            "employers never switch category."
        ),
        "source": "https://www.gov.uk/government/statistics/tax-reliefs/tax-relief-statistics-january-2026",
    },
    "lfs_employment": {
        "employment_18_24": 3_444_000,
        "employment_rate_18_24": 0.586,
        "period_label": "Jan-Mar 2026",
        "release_label": "ONS A05 SA, May 2026 release",
        "description": (
            "LFS employment level and rate, ages 18-24, UK, seasonally "
            "adjusted (ONS dataset A05 SA). LFS employment includes the "
            "self-employed; the model counts employees with positive "
            "employment income only."
        ),
        "source": "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/employmentunemploymentandeconomicinactivitybyagegroupseasonallyadjusteda05sa",
    },
    "ashe_earnings": {
        "mean_annual_pay_18_21": 15_254,
        "mean_annual_pay_22_29": 31_719,
        "median_annual_pay_18_21": 13_069,
        "median_annual_pay_22_29": 29_855,
        "period_label": "April 2025 (provisional)",
        "description": (
            "ASHE Table 6.7a (2025 provisional): gross annual pay, all "
            "employees (full- and part-time) by age band. ASHE samples "
            "employee jobs on PAYE in April, so it misses part-year jobs "
            "that the model's annual income measure includes."
        ),
        "source": "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/agegroupashetable6",
    },
    "rti": {
        "payrolled_total_latest": 30_200_000,
        "payrolled_under_25_change_yoy": -55_000,
        "period_label": "April 2026",
        "description": "HMRC PAYE Real Time Information payrolled employees.",
        "source": "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/bulletins/earningsandemploymentfrompayasyouearnrealtimeinformationuk/latest",
    },
    "obr": {
        "initial_pass_through": 0.60,
        "initial_year_label": "2025-26",
        "medium_term_pass_through": 0.76,
        "medium_term_year_label": "2026-27",
        "nics_rise_year": 2024,
        "description": (
            "OBR incidence assumptions for the Autumn Budget 2024 employer "
            "NICs rise (EFO October 2024)."
        ),
        "source": "https://obr.uk/efo/economic-and-fiscal-outlook-october-2024/",
    },
    "obr_nics_rise": {
        "static_yield_2025_26_bn": 23.9,
        "static_yield_2026_27_bn": 24.3,
        "post_behavioural_yield_2029_30_bn": 16.1,
        "labour_supply_effect_hours_equivalents": -50_000,
        "description": (
            "OBR supplementary forecast release (May 2025): HMRC's static "
            "costing of the April 2025 employer NICs package (15% rate, "
            "£5,000 Secondary Threshold, Employment Allowance changes), "
            "certified by the OBR — Table 1.5. The October 2024 EFO judged "
            "the rise would reduce labour supply by around 50,000 "
            "average-hours equivalents; the OBR publishes no youth-specific "
            "labour demand elasticity."
        ),
        "source": "https://obr.uk/supplementary-forecast-information-on-static-costing-of-changes-to-employer-national-insurance-contributions/",
    },
    "elasticity_evidence": {
        "egebark_kaunitz_2018": -0.31,
        "egebark_kaunitz_url": "https://doi.org/10.1016/j.labeco.2018.10.001",
        "lichter_2015_meta": -0.25,
        "lichter_url": "https://doi.org/10.1016/j.euroecorev.2015.08.007",
        "egebark_kaunitz_cost_per_job_multiple": 4,
        "description": (
            "Youth labour demand elasticities and cost-per-job from the "
            "Swedish under-26 payroll tax cut literature."
        ),
        "source": "https://doi.org/10.1016/j.labeco.2018.10.001",
    },
}


def as_json() -> dict:
    """Everything above, serialised for the results JSON."""
    return {
        "reform_definition": {
            "reform_age_lower": REFORM_AGE_LOWER,
            "reform_age_upper": REFORM_AGE_UPPER,
            "marginal_age_lower": MARGINAL_AGE_LOWER,
        },
        "assumptions": {
            "pass_through_scenarios": [asdict(s) for s in PASS_THROUGH_SCENARIOS],
            "demand_elasticities": {k: asdict(v) for k, v in DEMAND_ELASTICITIES.items()},
            "calculator_annual_rent": asdict(CALCULATOR_ANNUAL_RENT),
        },
        "statutory_unmodelled": {
            "employment_allowance": asdict(EMPLOYMENT_ALLOWANCE),
            **{k: asdict(v) for k, v in EXISTING_RELIEFS.items()},
        },
        "official_stats": OFFICIAL_STATS,
    }
