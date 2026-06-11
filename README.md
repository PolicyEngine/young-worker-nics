# Employer NICs exemption for young workers (18-24)

**Live dashboard: [young-worker-nics.vercel.app](https://young-worker-nics.vercel.app)**

Data pipeline and dashboard estimating the fiscal cost, distributional impact
and employment effects of extending the employer NICs zero rate — which
already covers under-21s (category M, since April 2015) and apprentices under
25 (category H, since April 2016) — to **all employees aged 18 to 24**, on
earnings up to the Upper Secondary Threshold. Built with the
[PolicyEngine UK](https://policyengine.org) microsimulation model on the
enhanced Family Resources Survey.

## Headline results (2027-28 parameters)

| Result | Value |
| --- | --- |
| Static cost (employed 21-24s, the marginal population) | £7.68bn/year |
| Employees newly exempt | 2.36m |
| Average employer NICs forgone per employee | £3,253/year |
| Net cost at 25% / 60% / 76% wage pass-through | £7.13bn / £6.35bn / £6.00bn |
| Jobs at demand elasticity −0.15 / −0.31 / −0.50 | +37k / +76k / +123k |
| Static cost per additional job (central) | ~£101k |

Under-21s are already zero-rated in law, so the Exchequer-relevant cost comes
from employed 21-24-year-olds. The static cost is validated against a
PolicyEngine Reform-object simulation at build time (the build fails if they
diverge by more than 0.1%) and reconciled against official statistics: HMRC
scores the existing under-21 relief at
[£1.9bn for 2025-26](https://www.gov.uk/government/statistics/tax-reliefs/tax-relief-statistics-january-2026)
(the model's 18-20 band is £2.1bn), the LFS counts
[3.44m employed 18-24-year-olds](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/employmentunemploymentandeconomicinactivitybyagegroupseasonallyadjusteda05sa)
(the model has 3.2m employees), and the implied mean pay of employed 21-24s
sits between the
[ASHE](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/agegroupashetable6)
means for the 18-21 and 22-29 bands.

## What the analysis covers

- **Static cost** — employer NICs forgone on each employed 21-24-year-old:
  the statutory rate times NICable earnings between the Secondary Threshold
  and the Upper Secondary Threshold (15%, £4,992 and £50,270 for 2027-28, all
  read from the PolicyEngine parameter tree). Breakdowns by income quintile,
  quartile and decile, single year of age, gender and country.
- **Wage pass-through scenarios** — for each pass-through rate (0%, 25%, 60%,
  76%), every treated worker's employment income is raised by that share of
  their employer's saving and a full microsimulation is re-run, so income
  tax, employee NICs and benefit withdrawal are computed person by person.
  The 60% and 76% rates mirror the
  [OBR's incidence assumptions](https://obr.uk/efo/economic-and-fiscal-outlook-october-2024/)
  for the 2024 employer NICs rise; the age-targeted evidence
  ([Saez, Schoefer & Seim 2019](https://www.aeaweb.org/articles?id=10.1257/aer.20171937))
  found approximately zero pass-through to targeted workers' own wages.
- **Poverty and distributional impacts** — change in BHC absolute poverty
  (all people and 18-24s, household-level), people lifted out of poverty, and
  the average household net income change by baseline income quintile,
  quartile and decile.
- **Labour demand scenarios** — employment gains among treated 21-24s from
  the ~10% fall in employment costs, at elasticities of −0.15 / −0.31 / −0.50
  ([Egebark & Kaunitz 2018](https://doi.org/10.1016/j.labeco.2018.10.001);
  [Lichter, Peichl & Siegloch 2015](https://doi.org/10.1016/j.euroecorev.2015.08.007)).
  Scenario arithmetic, not a forecast.
- **Household calculator** (opt-in) — what the exemption is worth on a single
  young worker, by gross salary, age, location and housing status.

Every number on the dashboard comes from the results JSON; every non-PolicyEngine
assumption carries a value, description and source URL in
`src/young_worker_nics/sources.py`, cited inline where the dashboard uses it.
The pipeline stamps the `policyengine` bundle version it ran on into the JSON
(the `[uk]` extra exact-pins `policyengine-uk`, so that one version identifies
the whole simulation stack); the dashboard footer displays it.

## Policy context

- ONS: 1,012,000 16-24-year-olds (13.5%) were NEET in January-March 2026, up
  89,000 on a year earlier ([ONS NEET bulletin, May 2026](https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment/bulletins/youngpeoplenotineducationemploymentortrainingneet/may2026)).
- Autumn Budget 2024 raised the employer NICs rate to 15% and cut the
  Secondary Threshold to £5,000 from April 2025, a package HMRC scores at
  [£24.3bn static in 2026-27](https://obr.uk/supplementary-forecast-information-on-static-costing-of-changes-to-employer-national-insurance-contributions/)
  ([NICs (Secondary Class 1 Contributions) Act 2025](https://www.legislation.gov.uk/ukpga/2025/11)).
- Current rates and thresholds: [gov.uk, 2026-27](https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027).

## Quick start

```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[simulation,dev]"

# HUGGING_FACE_TOKEN required for the enhanced-FRS microdata
python -m young_worker_nics --year 2027

# options (defaults shown)
python -m young_worker_nics \
  --year 2027 \
  --pass-through 0 0.25 0.6 0.76 \
  --demand-elasticity-low -0.15 \
  --demand-elasticity-central -0.31 \
  --demand-elasticity-high -0.50 \
  --include-calculator \
  --calculator-rent 9600
```

Outputs `data/young_worker_nics_results.json` and a copy under
`dashboard/public/data/` for the dashboard.

## Dashboard

```bash
cd dashboard
bun install
bun run dev
```

Next.js (App Router) + Recharts + Tailwind, PolicyEngine design system tokens.
Three tabs: the reform results (static and behavioural views), a youth labour
market baseline reconciling the model with official statistics, and a
methodology page with the method notes the pipeline writes alongside the
results.

## Tests

```bash
pytest  # pure-Python statutory arithmetic; no microdata needed
```

Linting and the dashboard build run in CI on every pull request.

## Key caveats

- The PolicyEngine UK baseline does not model the existing under-21 or
  apprentice zero rates; the costing restricts to ages 21-24, where the
  baseline is correct.
- Apprentices under 25 are already exempt in law but the FRS microdata
  records no apprenticeship status, so they are not modelled — the marginal
  cost is overstated on that margin, with no adjustment applied anywhere.
- Employment Allowance interactions are not modelled (no employer-side data
  in the FRS), so the static cost is overstated on that margin too.
- Enhanced-FRS calibration constrains 10-year age bands, not single years of
  age, so single-age breakdowns are indicative; band-level results are solid.
- Labour demand responses are scenario-based and partial-equilibrium:
  substitution against workers just outside the age band,
  general-equilibrium effects and the transplant of Swedish elasticities to
  the UK are not captured.
