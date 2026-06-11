"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { colors } from "../lib/colors";
import {
  formatBn,
  formatCount,
  formatCurrency,
  formatPct,
} from "../lib/formatters";
import {
  getCalculatorProfile,
  getEmploymentScenarios,
  getPassThroughScenarios,
  getStatic,
} from "../lib/dataHelpers";
import ChartLogo from "./ChartLogo";
import SectionHeading from "./SectionHeading";

const AXIS_STYLE = { fontSize: 12, fill: colors.gray[500] };

// The Household view exists only when the pipeline was run with
// --include-calculator; the JSON carries person_calculator: null otherwise.
const SUB_TABS = (hasCalculator) => [
  ...(hasCalculator ? [{ id: "household", label: "Household" }] : []),
  { id: "static", label: "Population (static)" },
  { id: "behavioural", label: "Population (behavioural)" },
];

const DIMENSIONS = [
  { id: "by_income_quintile", label: "Income quintile" },
  { id: "by_income_quartile", label: "Income quartile" },
  { id: "by_income_decile", label: "Income decile" },
  { id: "by_age", label: "Age" },
  { id: "by_gender", label: "Gender" },
  { id: "by_country", label: "Country" },
];

function MetricCard({ label, value, note }) {
  return (
    <div className="metric-card">
      <p className="text-sm font-semibold leading-snug text-slate-700">
        {label}
      </p>
      <p className="mt-1 text-3xl font-bold">{value}</p>
      {note && (
        <p className="mt-2 border-t border-slate-100 pt-2 text-xs leading-5 text-slate-500">
          {note}
        </p>
      )}
    </div>
  );
}

function SwitchRow({ label, children }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-28 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </span>
      {children}
    </div>
  );
}

function HouseholdView({ data }) {
  const ages = data.person_calculator.ages;
  const [age, setAge] = useState(ages[Math.floor((ages.length - 1) / 2)]);
  const [region, setRegion] = useState("ruk");
  const [renter, setRenter] = useState(false);
  const profile = getCalculatorProfile(data, age, region, renter);

  const chartData = profile.employment_income.map((income, i) => ({
    income,
    saving: profile.employer_nics_saving[i],
    netGain: profile.net_gain_full_passthrough[i],
    net: profile.net[i],
    benefits: profile.benefits[i],
  }));

  const switches = (
    <div className="mb-4 space-y-2">
      <SwitchRow label="Age">
        {ages.map((a) => (
          <button
            key={a}
            className={`selector-chip compact ${age === a ? "active" : ""}`}
            onClick={() => setAge(a)}
          >
            {a}
          </button>
        ))}
      </SwitchRow>
      <SwitchRow label="Location">
        {Object.keys(data.person_calculator.regions).map((r) => (
          <button
            key={r}
            className={`selector-chip compact ${region === r ? "active" : ""}`}
            onClick={() => setRegion(r)}
          >
            {r === "ruk" ? "Rest of UK" : "Scotland"}
          </button>
        ))}
      </SwitchRow>
      <SwitchRow label="Housing">
        {[false, true].map((r) => (
          <button
            key={String(r)}
            className={`selector-chip compact ${renter === r ? "active" : ""}`}
            onClick={() => setRenter(r)}
          >
            {r ? "Private renter" : "Not renting"}
          </button>
        ))}
      </SwitchRow>
    </div>
  );

  return (
    <>
      <section className="section-card">
        <SectionHeading
          title="Exemption value for a single worker"
          description={`Employer NICs saved on a ${age}-year-old employee by gross salary, and the worker's exact net gain if the saving were fully passed through as wages. With ${formatPct(data.settings.pass_through_scenarios[0] * 100, 0)} pass-through the worker line is flat at zero and the employer keeps the saving.`}
        />
        {switches}
        <div className="h-[380px] w-full">
          <ResponsiveContainer>
            <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} />
              <XAxis
                dataKey="income"
                tick={AXIS_STYLE}
                tickFormatter={formatCurrency}
                label={{ value: "Gross salary", position: "insideBottom", offset: -2, fontSize: 12 }}
              />
              <YAxis
                tick={AXIS_STYLE}
                tickFormatter={formatCurrency}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip formatter={(v) => formatCurrency(v)} />
              <Legend />
              <Line
                type="monotone"
                dataKey="saving"
                name="Employer NICs saved"
                stroke={colors.primary[600]}
                strokeWidth={2.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="netGain"
                name="Worker net gain (100% pass-through)"
                stroke={colors.primary[700]}
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <ChartLogo />
      </section>

      <section className="section-card">
        <SectionHeading
          title="Baseline net income and benefits"
          description="The worker's household net income by gross salary, with the benefits component shown separately (benefits are part of net income, not additional to it). These are the curves the switches above reshape: UC eligibility and housing element, Scottish income tax, minimum wage bands by age."
        />
        <div className="h-[380px] w-full">
          <ResponsiveContainer>
            <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} />
              <XAxis
                dataKey="income"
                tick={AXIS_STYLE}
                tickFormatter={formatCurrency}
                label={{ value: "Gross salary", position: "insideBottom", offset: -2, fontSize: 12 }}
              />
              <YAxis
                tick={AXIS_STYLE}
                tickFormatter={formatCurrency}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip formatter={(v) => formatCurrency(v)} />
              <Legend />
              <Line
                type="monotone"
                dataKey="net"
                name="Household net income"
                stroke={colors.primary[600]}
                strokeWidth={2.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="benefits"
                name="Benefits (component of net income)"
                stroke={colors.primary[700]}
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <ChartLogo />
      </section>
    </>
  );
}

function TipHeader({ label, tip }) {
  return (
    <th>
      {label}{" "}
      <span className="info-tip" tabIndex={0}>
        i<span className="info-tip-bubble">{tip}</span>
      </span>
    </th>
  );
}

function SourceLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="underline">
      {children}
    </a>
  );
}

function StaticView({ data }) {
  const [dimension, setDimension] = useState("by_income_quintile");
  const staticResults = getStatic(data);
  const rows = staticResults[dimension];
  const params = data.nics_parameters;
  const rate = formatPct(params.employer_rate * 100);
  const reliefs = data.statutory_unmodelled;
  const hmrc = data.official_stats.hmrc_relief;
  const lfs = data.official_stats.lfs_employment;

  return (
    <>
      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="The proposed reform"
          description={`Employers currently pay NICs at ${rate} on each employee's earnings above the Secondary Threshold (${formatCurrency(params.secondary_threshold_annual)}/year). The reform switches that charge off for all employees aged 18-24 on earnings up to the Upper Secondary Threshold (${formatCurrency(params.upper_secondary_threshold_annual)}/year) — the same design as the existing zero rates for under-21s and apprentices under 25, extended to the whole age group. Nothing changes for the worker's own NICs or take-home pay; the saving goes to the employer.`}
        />
      </div>

      <section className="section-card">
        <SectionHeading
          title="Treatment by employee group"
          description="The bold row is the only change; every other group keeps its current treatment."
        />
        <table className="data-table">
          <thead>
            <tr>
              <th>Employee group</th>
              <th>Earnings band</th>
              <th>Employer NICs today</th>
              <th>Under the reform</th>
            </tr>
          </thead>
          <tbody>
            <tr className="font-semibold">
              <td>Aged 21-24</td>
              <td>Secondary to Upper Secondary Threshold</td>
              <td>{rate}</td>
              <td>0% — the change</td>
            </tr>
            <tr>
              <td>Under 21</td>
              <td>Secondary to Upper Secondary Threshold</td>
              <td>
                0% (already exempt,{" "}
                <SourceLink href={reliefs.under_21_relief.url}>
                  category M
                </SourceLink>
                )
              </td>
              <td>0% (unchanged)</td>
            </tr>
            <tr>
              <td>Apprentices under 25*</td>
              <td>Secondary to Upper Secondary Threshold</td>
              <td>
                0% (already exempt,{" "}
                <SourceLink href={reliefs.apprentice_relief.url}>
                  category H
                </SourceLink>
                )
              </td>
              <td>0% (unchanged)</td>
            </tr>
            <tr>
              <td>Aged 18-24</td>
              <td>Above the Upper Secondary Threshold</td>
              <td>{rate}</td>
              <td>{rate} (unchanged)</td>
            </tr>
            <tr>
              <td>Aged 25 and over</td>
              <td>Above the Secondary Threshold</td>
              <td>{rate}</td>
              <td>{rate} (unchanged)</td>
            </tr>
          </tbody>
        </table>
        <details className="mt-2 text-xs text-slate-500">
          <summary className="cursor-pointer">
            * Why apprentices are not separated out in the model
          </summary>
          <p className="mt-1">
            PolicyEngine UK defines an apprentice flag, but the Family
            Resources Survey microdata behind it records no apprenticeship
            status, so the flag is false for every person and apprentices
            cannot be separated from other employees. Their relief is existing
            law and is not counted in the reform&apos;s cost.
          </p>
        </details>
      </section>

      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="Static fiscal cost"
          description={`Static means wages, employment and behaviour are held fixed: the cost is simply the employer NICs no longer charged in ${data.fiscal_year_label}, computed person by person on the PolicyEngine UK enhanced FRS. Under-21s are already exempt in law, so the marginal cost comes from employed 21-24-year-olds. What happens when employers respond is in the Population (behavioural) view.`}
        />
      </div>

      <section className="section-card">
        <SectionHeading
          title="Headline results"
          description={`Figures are for ${data.fiscal_year_label}. Each card notes the nearest official benchmark.`}
        />
        <div className="grid gap-4 md:grid-cols-3">
          <MetricCard
            label="Static cost — relieved band for employed 21-24s"
            value={formatBn(staticResults.marginal_cost_bn)}
            note={
              <>
                Compare: <SourceLink href={hmrc.source}>HMRC</SourceLink>{" "}
                scores the existing under-21 zero rate at{" "}
                {formatBn(hmrc.under_21_relief_forecast_2025_26_bn)} for{" "}
                {hmrc.forecast_period_label}.
              </>
            }
          />
          <MetricCard
            label="Employees newly exempt — employed 21-24-year-olds"
            value={formatCount(staticResults.n_marginal_employees)}
            note={
              <>
                Compare: {formatCount(lfs.employment_18_24)} 18-24-year-olds in
                employment, {lfs.period_label} (ONS{" "}
                <SourceLink href={lfs.source}>LFS</SourceLink>), which includes
                the self-employed and 18-20-year-olds.
              </>
            }
          />
          <MetricCard
            label="Average employer NICs saving per newly exempt employee"
            value={formatCurrency(staticResults.avg_saving_per_employee)}
          />
        </div>
      </section>

      <section className="section-card">
        <SectionHeading
          title="Detailed breakdown"
          description={`Employer NICs forgone in ${data.fiscal_year_label} in the relieved band across all 18-24-year-old employees, split by group. Group totals sum to the full 18-24 quantum of ${formatBn(staticResults.headline_quantum_bn)} — larger than the ${formatBn(staticResults.marginal_cost_bn)} headline cost because they include 18-20-year-olds, whose relief is already law.${dimension === "by_age" ? ` ${data.age_band_note}` : ""}`}
        />
        <div className="mb-4 flex flex-wrap gap-2">
          {DIMENSIONS.map((d) => (
            <button
              key={d.id}
              className={`selector-chip compact ${dimension === d.id ? "active" : ""}`}
              onClick={() => setDimension(d.id)}
            >
              {d.label}
            </button>
          ))}
        </div>
        <div className="h-[380px] w-full">
          <ResponsiveContainer>
            <BarChart data={rows} margin={{ top: 10, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} />
              <XAxis dataKey="group" tick={AXIS_STYLE} />
              <YAxis
                tick={AXIS_STYLE}
                tickFormatter={(v) => formatBn(v)}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip formatter={(v) => formatBn(v)} />
              <Bar
                dataKey="static_cost_bn"
                name="Static cost"
                fill={colors.primary[600]}
                radius={[6, 6, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <ChartLogo />
      </section>
    </>
  );
}

function BehaviouralView({ data }) {
  const passThrough = getPassThroughScenarios(data);
  const employment = getEmploymentScenarios(data);
  const obr = data.official_stats.obr;
  const evidence = data.official_stats.elasticity_evidence;
  const [scenarioRate, setScenarioRate] = useState(
    (
      passThrough.find(
        (s) => s.pass_through_rate === obr.medium_term_pass_through
      ) ||
      passThrough.find((s) => s.pass_through_rate > 0) ||
      passThrough[0]
    ).pass_through_rate
  );
  const [grouping, setGrouping] = useState("quintiles");
  const scenario = passThrough.find(
    (s) => s.pass_through_rate === scenarioRate
  );

  return (
    <>
      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="Wage pass-through"
          description={
            <>
              The exemption is paid to employers, so the first behavioural
              question is what they do with the saving. Whatever share they pass
              to young workers as higher wages determines both who benefits and
              what the policy costs: passed-through wages are partly clawed back
              by the Exchequer through income tax, employee NICs and benefit
              withdrawal, shrinking the net cost below the{" "}
              {formatBn(passThrough[0].gross_cost_bn)} gross figure. Each
              scenario below re-runs the full microsimulation with wages boosted
              by that share of the saving. The default selection,{" "}
              {formatPct(obr.medium_term_pass_through * 100, 0)}, is the
              medium-term incidence assumption of the{" "}
              <SourceLink href={obr.source}>OBR</SourceLink> for the{" "}
              {obr.nics_rise_year} employer NICs rise (
              {formatPct(obr.initial_pass_through * 100, 0)} in its first year);
              the age-targeted{" "}
              <SourceLink href={data.assumptions.pass_through_scenarios[0].url}>
                evidence
              </SourceLink>{" "}
              (Saez, Schoefer &amp; Seim 2019) supports the lower{" "}
              {formatPct(data.settings.pass_through_scenarios[1] * 100, 0)}.
            </>
          }
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
          Pass-through rate
        </span>
        {passThrough.map((s) => {
          const pct = formatPct(s.pass_through_rate * 100, 0);
          const tag =
            s.pass_through_rate === 0
              ? " (static assumption)"
              : s.pass_through_rate === obr.initial_pass_through
                ? " (OBR initial)"
                : s.pass_through_rate === obr.medium_term_pass_through
                  ? " (OBR medium-term)"
                  : "";
          return (
            <button
              key={s.pass_through_rate}
              className={`selector-chip compact ${
                scenarioRate === s.pass_through_rate ? "active" : ""
              }`}
              onClick={() => setScenarioRate(s.pass_through_rate)}
            >
              {pct}
              {tag}
            </button>
          );
        })}
      </div>

      <section className="section-card">
        <SectionHeading
          title="Net Exchequer cost by pass-through rate"
          description={`Each row is a full microsimulation run for ${data.fiscal_year_label}. The more of the saving that reaches wages, the more flows back in tax and withdrawn benefits, and the lower the net cost. The bold row is the scenario selected above.`}
        />
        <table className="data-table">
          <thead>
            <tr>
              <TipHeader
                label="Pass-through"
                tip="Share of the employer NICs saving passed to treated workers as higher wages."
              />
              <TipHeader
                label="Gross cost"
                tip="Employer NICs forgone in the relieved band, before any revenue flows back to the Exchequer."
              />
              <TipHeader
                label="Fiscal offset"
                tip="Revenue recouped on the passed-through wages: income tax, employee NICs and benefits withdrawn as incomes rise."
              />
              <TipHeader
                label="Net cost"
                tip="Gross cost minus the fiscal offset."
              />
              <TipHeader
                label="Avg wage gain"
                tip="Average annual wage increase per treated 21-24-year-old employee under this scenario."
              />
            </tr>
          </thead>
          <tbody>
            {passThrough.map((row) => (
              <tr
                key={row.pass_through_rate}
                className={
                  row.pass_through_rate === scenarioRate ? "font-semibold" : ""
                }
              >
                <td>{formatPct(row.pass_through_rate * 100, 0)}</td>
                <td>{formatBn(row.gross_cost_bn)}</td>
                <td>{formatBn(row.fiscal_offset_bn)}</td>
                <td>{formatBn(row.net_cost_bn)}</td>
                <td>{formatCurrency(row.avg_wage_gain)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="section-card">
        <SectionHeading
          title="Composition of the fiscal offset"
          description={`Decomposition of the fiscal offset under the selected ${formatPct(scenario.pass_through_rate * 100, 0)} pass-through scenario. With zero pass-through no saving reaches workers' pay, so there is no offset, poverty or distributional effect to show — those results exist only for the scenarios with positive pass-through.`}
        />
        {scenario.pass_through_rate > 0 && (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Line item</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Gross cost (employer NICs forgone)</td>
                  <td>{formatBn(scenario.gross_cost_bn)}</td>
                </tr>
                <tr>
                  <td>Income tax on passed-through wages</td>
                  <td>{formatBn(scenario.offset_components_bn.income_tax)}</td>
                </tr>
                <tr>
                  <td>Employee NICs on passed-through wages</td>
                  <td>
                    {formatBn(scenario.offset_components_bn.employee_nics)}
                  </td>
                </tr>
                <tr>
                  <td>Benefits saved</td>
                  <td>
                    {formatBn(scenario.offset_components_bn.benefits_saved)}
                  </td>
                </tr>
                <tr>
                  <td className="font-semibold">Total fiscal offset</td>
                  <td className="font-semibold">
                    {formatBn(scenario.fiscal_offset_bn)}
                  </td>
                </tr>
                <tr>
                  <td className="font-semibold">Net Exchequer cost</td>
                  <td className="font-semibold">
                    {formatBn(scenario.net_cost_bn)}
                  </td>
                </tr>
                <tr>
                  <td>Average wage gain per treated employee</td>
                  <td>{formatCurrency(scenario.avg_wage_gain)}</td>
                </tr>
              </tbody>
            </table>
          </>
        )}
      </section>

      {scenario.pass_through_rate > 0 && (
        <section className="section-card">
          <SectionHeading
            title="Poverty impact"
            description={`Absolute poverty before housing costs in ${data.fiscal_year_label} under the ${formatPct(scenario.pass_through_rate * 100, 0)} pass-through scenario, baseline versus reform. Poverty is measured on household income, so people who share a household with a young worker whose pay rises can move out of poverty too.`}
          />
          <div className="grid gap-4 md:grid-cols-3">
            <MetricCard
              label="Poverty rate change, all people (absolute, before housing costs)"
              value={`${((scenario.poverty.reformed_rate_bhc - scenario.poverty.baseline_rate_bhc) * 100).toFixed(2)}pp`}
            />
            <MetricCard
              label="Poverty rate change, 18-24 (absolute, before housing costs)"
              value={`${((scenario.poverty.reformed_rate_bhc_18_24 - scenario.poverty.baseline_rate_bhc_18_24) * 100).toFixed(2)}pp`}
            />
            <MetricCard
              label="People lifted out of poverty"
              value={formatCount(scenario.poverty.people_lifted)}
              note={`${formatCount(scenario.poverty.people_lifted_18_24)} are themselves aged 18-24; the rest share a household with a young worker whose pay rises.`}
            />
          </div>
        </section>
      )}

      {scenario.pass_through_rate > 0 && (
        <section className="section-card">
          <SectionHeading
            title="Average household net income change"
            description={`Weighted average change in household net income in ${data.fiscal_year_label} under the ${formatPct(scenario.pass_through_rate * 100, 0)} pass-through scenario, across all households in each baseline income group (gainers and non-gainers alike).`}
          />
          <div className="mb-4 flex flex-wrap gap-2">
            {["quintiles", "quartiles", "deciles"].map((g) => (
              <button
                key={g}
                className={`selector-chip compact capitalize ${grouping === g ? "active" : ""}`}
                onClick={() => setGrouping(g)}
              >
                {g}
              </button>
            ))}
          </div>
          <div className="h-[380px] w-full">
            <ResponsiveContainer>
              <BarChart
                data={scenario.avg_change_by_group[grouping]}
                margin={{ top: 10, right: 20, bottom: 5, left: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} />
                <XAxis
                  dataKey="group"
                  tick={AXIS_STYLE}
                  label={{
                    value: `Income ${grouping.slice(0, -1)} (1 = lowest income)`,
                    position: "insideBottom",
                    offset: -2,
                    fontSize: 12,
                  }}
                />
                <YAxis
                  tick={AXIS_STYLE}
                  tickFormatter={(v) => formatCurrency(v)}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  formatter={(v, name, item) => [
                    `${formatCurrency(v)}/year (total ${formatBn(item.payload.total_change_bn)})`,
                    "Avg change per household",
                  ]}
                  labelFormatter={(label) => `${grouping.slice(0, -1)} ${label}`}
                />
                <Bar
                  dataKey="avg_change_per_household"
                  name="Avg change per household"
                  fill={colors.primary[600]}
                  radius={[6, 6, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ChartLogo />
        </section>
      )}

      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="Labour demand response"
          description={
            <>
              Pass-through decides who keeps the money; the demand response asks
              whether cheaper youth labour changes hiring. Whatever employers do
              not pass on lowers the total cost of employing a 21-24-year-old,
              and the youth payroll-tax literature provides demand elasticities
              that translate that cost fall into additional jobs. The two
              channels trade off against each other — money passed to wages
              cannot also cut employment costs — so this section and the
              pass-through section bracket the policy&apos;s possible effects
              rather than adding together. The elasticity arithmetic leaves out
              substitution from workers just outside the age band, wider
              economy-wide responses, and differences between the Swedish
              setting it was estimated in and the UK (see the model{" "}
              <Link
                href="/?tab=methodology#model-omissions"
                className="underline"
              >
                limitations
              </Link>
              ); the job numbers are scenario arithmetic, not a forecast.
            </>
          }
        />
      </div>

      <section className="section-card">
        <SectionHeading
          title="Employment effect by demand elasticity"
          description={
            <>
              Employment gain among treated 21-24-year-olds in{" "}
              {data.fiscal_year_label} from the fall in employment costs,
              across demand elasticity scenarios (Egebark
              &amp; Kaunitz 2018:{" "}
              <SourceLink href={evidence.egebark_kaunitz_url}>
                {evidence.egebark_kaunitz_2018}
              </SourceLink>
              ; Lichter et al. 2015 meta-analysis:{" "}
              <SourceLink href={evidence.lichter_url}>
                {evidence.lichter_2015_meta}
              </SourceLink>
              ). In the Swedish evidence, most of
              the fiscal cost subsidised jobs that would have existed anyway, at
              roughly {evidence.egebark_kaunitz_cost_per_job_multiple} times the
              direct cost of employing a young worker per additional job.
              {data.official_stats.obr_nics_rise && (
                <>
                  {" "}
                  The OBR publishes no youth-specific demand elasticity; for
                  the {data.official_stats.obr.nics_rise_year} employer NICs
                  rise it judged that labour supply would fall by around{" "}
                  <SourceLink href={data.official_stats.obr_nics_rise.source}>
                    {formatCount(
                      Math.abs(
                        data.official_stats.obr_nics_rise
                          .labour_supply_effect_hours_equivalents
                      )
                    )}
                  </SourceLink>{" "}
                  average-hours equivalents, the same cost channel in the
                  opposite direction.
                </>
              )}
            </>
          }
        />
        <table className="data-table">
          <thead>
            <tr>
              {[
                {
                  label: "Scenario",
                  tip: "Low, central and high refer to the size of the assumed labour demand response, not to better or worse outcomes.",
                },
                {
                  label: "Elasticity",
                  tip: "Percentage change in youth employment for a one per cent change in the cost of employing a young worker, from the studies cited above.",
                },
                {
                  label: "Avg cost wedge",
                  tip: "Average percentage fall in the total cost of employing a 21-24-year-old (gross pay plus employer NICs) once the zero rate applies.",
                },
                {
                  label: "Employment gain",
                  tip: "Elasticity times average cost wedge: the percentage increase in 21-24 employment under this scenario.",
                },
                {
                  label: "New jobs",
                  tip: "Employment gain applied to the weighted count of employed 21-24-year-olds.",
                },
                {
                  label: "Static cost per job",
                  tip: "Static cost divided by new jobs. It counts the subsidy paid on all existing jobs, which is why it is a multiple of a young worker's salary.",
                },
              ].map((col) => (
                <TipHeader key={col.label} label={col.label} tip={col.tip} />
              ))}
            </tr>
          </thead>
          <tbody>
            {employment.map((row) => (
              <tr key={row.scenario}>
                <td className="capitalize">{row.scenario}</td>
                <td>{row.demand_elasticity}</td>
                <td>{formatPct(row.avg_cost_wedge_pct * 100)}</td>
                <td>{formatPct(row.employment_gain_pct * 100)}</td>
                <td>{formatCount(row.new_jobs)}</td>
                <td>{formatCurrency(row.static_cost_per_job)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

export default function ReformTab({ data }) {
  const hasCalculator = data.person_calculator !== null;
  const [subTab, setSubTab] = useState(hasCalculator ? "household" : "static");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {SUB_TABS(hasCalculator).map((tab) => (
          <button
            key={tab.id}
            className={`toggle-button ${subTab === tab.id ? "active" : ""}`}
            onClick={() => setSubTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {subTab === "household" && <HouseholdView data={data} />}
      {subTab === "static" && <StaticView data={data} />}
      {subTab === "behavioural" && <BehaviouralView data={data} />}
    </div>
  );
}
