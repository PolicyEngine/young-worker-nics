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
  getEmploymentScenarios,
  getPassThroughScenarios,
  getStatic,
} from "../lib/dataHelpers";
import ChartLogo from "./ChartLogo";
import SectionHeading from "./SectionHeading";

const AXIS_STYLE = { fontSize: 12, fill: colors.gray[500] };

// Labour demand response is hidden for now but fully computed by the
// pipeline and present in the JSON — flip to true to bring the section back.
const SHOW_LABOUR_DEMAND = false;

const SUB_TABS = [
  { id: "static", label: "Population (static)" },
  { id: "behavioural", label: "Population (behavioural)" },
];

// Quintile and decile splits are in the JSON but not offered in the UI.
const DIMENSIONS = [
  { id: "by_income_quartile", label: "Income quartile" },
  { id: "by_age", label: "Age" },
  { id: "by_gender", label: "Gender" },
  { id: "by_country", label: "Country" },
  { id: "by_region", label: "Region" },
];

// Small fiscal lines (e.g. benefits saved) round to £0.0bn at one decimal;
// show them in £m instead of dropping a real non-zero line.
function formatBnFine(value) {
  return Math.abs(value) < 0.05 ? `£${Math.round(value * 1000)}m` : formatBn(value);
}

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

function NotComputedNote() {
  return (
    <p className="text-sm text-slate-500">
      Not computed for the targeted population.
    </p>
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

function StaticView({ data, targeted, excludePublic }) {
  const dimensions = DIMENSIONS;
  const [dimension, setDimension] = useState("by_income_quartile");
  // `targeted` mirrors the data.reform schema; the pipeline may omit some
  // breakdowns for the targeted population, so every access is null-guarded.
  // `excludePublic` swaps in the *_excl_public block (non-public employees
  // only), which carries the same breakdown shape.
  const staticResults = excludePublic
    ? (targeted ? (targeted.static_excl_public ?? null) : (data.reform.static_excl_public ?? null))
    : (targeted ? (targeted.static ?? null) : getStatic(data));
  const allRows = staticResults?.[dimension];
  // The targeted population has no under-21s (their relief is already law);
  // their age rows carry exactly zero weight, so drop empty groups.
  const rows =
    targeted && dimension === "by_age" && Array.isArray(allRows)
      ? allRows.filter((row) => row.n_employees > 0)
      : allRows;
  const params = data.nics_parameters;
  const rate = formatPct(params.employer_rate * 100);
  const reliefs = data.statutory_unmodelled;
  const hmrc = data.official_stats.hmrc_relief;
  const lfs = data.official_stats.lfs_employment;
  // Group splits spread the total thinly; one decimal would round the
  // smaller groups to £0.0bn.
  const breakdownMoney = (v) => `£${Number(v).toFixed(2)}bn`;
  // Appended to the section copy when the public-sector employers are
  // excluded, so the text matches the *_excl_public figures on screen.
  const publicScopeNote = excludePublic
    ? " Public-sector employers are excluded here: employer NICs on a public-sector job (NHS, state schools, councils, civil service, armed forces) are paid by government to government, so exempting them nets out of the consolidated public finances. The figures cover non-public employees only."
    : "";

  return (
    <>
      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="The proposed reform"
          description={
            targeted
              ? `Employers currently pay NICs at ${rate} on each employee's earnings above the Secondary Threshold (${formatCurrency(params.secondary_threshold_annual)}/year). The targeted reform switches that charge off only for employees aged 21-24 who were NEET (not in employment, education or training) at some point in the past year, on earnings up to the Upper Secondary Threshold (${formatCurrency(params.upper_secondary_threshold_annual)}/year). The same relief design as the existing zero rates for under-21s and apprentices under 25, but aimed at recent labour-market entrants rather than the whole age group. Nothing changes for the worker's own NICs or take-home pay; the saving goes to the employer.`
              : `Employers currently pay NICs at ${rate} on each employee's earnings above the Secondary Threshold (${formatCurrency(params.secondary_threshold_annual)}/year). The reform switches that charge off for all employees aged 18-24 on earnings up to the Upper Secondary Threshold (${formatCurrency(params.upper_secondary_threshold_annual)}/year), the same design as the existing zero rates for under-21s and apprentices under 25, extended to the whole age group. Nothing changes for the worker's own NICs or take-home pay; the saving goes to the employer.`
          }
        />
      </div>

      <section className="section-card">
        <SectionHeading
          title="Treatment by employee group"
          description="The bold row is the only change; every other group keeps its current treatment."
        />
        <details>
          <summary className="cursor-pointer text-sm font-medium text-slate-600">
            Show all groups
          </summary>
          <table className="data-table mt-3">
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
              <td>{targeted ? "Aged 21-24, NEET within the past year" : "Aged 21-24"}</td>
              <td>Secondary to Upper Secondary Threshold</td>
              <td>{rate}</td>
              <td>0%, the change</td>
            </tr>
            {targeted && (
              <tr>
                <td>Aged 21-24, not recently NEET</td>
                <td>Secondary to Upper Secondary Threshold</td>
                <td>{rate}</td>
                <td>{rate} (unchanged)</td>
              </tr>
            )}
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
        </details>
      </section>

      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="Static fiscal cost"
          description={
            targeted
              ? `Static means wages, employment and behaviour are held fixed: the cost is the employer NICs no longer charged in ${data.fiscal_year_label}, computed person by person in PolicyEngine UK, with each employed 21-24-year-old counted at their imputed probability of having been NEET within the past year. What happens when employers respond is in the Population (behavioural) view.${publicScopeNote}`
              : `Static means wages, employment and behaviour are held fixed: the cost is simply the employer NICs no longer charged in ${data.fiscal_year_label}, computed person by person in PolicyEngine UK. Under-21s are already exempt in law, so the marginal cost comes from employed 21-24-year-olds. What happens when employers respond is in the Population (behavioural) view.${publicScopeNote}`
          }
        />
      </div>

      <section className="section-card">
        <SectionHeading
          title={`Headline results, ${data.fiscal_year_label}`}
          description={
            targeted ? null : "Each card notes the nearest official benchmark."
          }
        />
        {staticResults?.marginal_cost_bn == null ? (
          <NotComputedNote />
        ) : (
        <div className="grid gap-4 md:grid-cols-3">
          <MetricCard
            label={
              targeted
                ? "Static cost: relieved band for recent-NEET employed 21-24s"
                : "Static cost: relieved band for employed 21-24s"
            }
            value={`£${Number(staticResults.marginal_cost_bn).toFixed(2)}bn`}
            note={
              targeted ? null : (
                <>
                  Compare: <SourceLink href={hmrc.source}>HMRC</SourceLink>{" "}
                  scores the existing under-21 zero rate at{" "}
                  {formatBn(hmrc.under_21_relief_forecast_2025_26_bn)} for{" "}
                  {hmrc.forecast_period_label}.
                </>
              )
            }
          />
          <MetricCard
            label={
              targeted
                ? "Employees newly exempt: recent-NEET employed 21-24-year-olds"
                : "Employees newly exempt: employed 21-24-year-olds"
            }
            value={
              staticResults.n_marginal_employees == null
                ? "—"
                : staticResults.n_marginal_employees >= 1e6
                  ? `${(staticResults.n_marginal_employees / 1e6).toFixed(2)}m`
                  : `${Math.round(staticResults.n_marginal_employees / 1e3)}k`
            }
            note={
              targeted ? null : (
                <>
                  Compare: {formatCount(lfs.employment_18_24)} 18-24-year-olds in
                  employment, {lfs.period_label} (ONS{" "}
                  <SourceLink href={lfs.source}>LFS</SourceLink>), which includes
                  the self-employed and 18-20-year-olds.
                </>
              )
            }
          />
          <MetricCard
            label="Average employer NICs saving per newly exempt employee"
            value={
              staticResults.avg_saving_per_employee != null
                ? formatCurrency(staticResults.avg_saving_per_employee)
                : "—"
            }
          />
        </div>
        )}
        {targeted && (
          <details className="mt-4">
            <summary className="cursor-pointer text-sm font-medium text-slate-600">
              How the recent-NEET population was estimated
            </summary>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              The ONS{" "}
              {data.official_stats.lfs_5q_panels?.survey_source ? (
                <SourceLink href={data.official_stats.lfs_5q_panels.survey_source}>
                  Labour Force Survey
                </SourceLink>
              ) : (
                "Labour Force Survey"
              )}{" "}
              interviews each respondent five times over a year, capturing who
              moved from NEET status (not in employment, education or training)
              into work.
              {targeted.lfs_panels != null && targeted.entrant_share != null && (
                <>
                  {" "}
                  Pooling {targeted.lfs_panels.count}{" "}
                  {data.official_stats.lfs_5q_panels?.source ? (
                    <SourceLink href={data.official_stats.lfs_5q_panels.source}>
                      five-quarter panels
                    </SourceLink>
                  ) : (
                    "five-quarter panels"
                  )}{" "}
                  ({targeted.lfs_panels.period}),{" "}
                  {formatPct(targeted.entrant_share * 100, 1)} of employed
                  21-24-year-olds were NEET at some point in the previous year.
                </>
              )}{" "}
              A quantile random forest trained on those members and calibrated
              to that share gives every employed 21-24-year-old their own
              probability of being such a recent entrant, from age, sex and
              earnings. Every figure above counts each employee at that
              probability; full detail is on the Methodology tab.
            </p>
          </details>
        )}
      </section>

      <section className="section-card">
        <SectionHeading
          title="Detailed breakdown"
          description={
            staticResults?.headline_quantum_bn != null &&
            staticResults?.marginal_cost_bn != null
              ? `Employer NICs forgone in ${data.fiscal_year_label} in the relieved band across all 18-24-year-old employees, split by group. Group totals sum to the full 18-24 quantum of ${formatBn(staticResults.headline_quantum_bn)}, larger than the ${formatBn(staticResults.marginal_cost_bn)} headline cost because they include 18-20-year-olds, whose relief is already law.${dimension === "by_age" ? ` ${data.age_band_note}` : ""}`
              : `Employer NICs forgone in ${data.fiscal_year_label} in the relieved band, split by group.${dimension === "by_age" ? ` ${data.age_band_note}` : ""}`
          }
        />
        <div className="mb-4 flex flex-wrap gap-2">
          {dimensions.map((d) => (
            <button
              key={d.id}
              className={`selector-chip compact ${dimension === d.id ? "active" : ""}`}
              onClick={() => setDimension(d.id)}
            >
              {d.label}
            </button>
          ))}
        </div>
        {Array.isArray(rows) && rows.length > 0 ? (
          <>
            <div className="h-[380px] w-full">
              <ResponsiveContainer>
                <BarChart data={rows} margin={{ top: 10, right: 20, bottom: 5, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} />
                  <XAxis dataKey="group" tick={AXIS_STYLE} />
                  <YAxis
                    tick={AXIS_STYLE}
                    tickFormatter={(v) => breakdownMoney(v)}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip formatter={(v) => breakdownMoney(v)} />
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
          </>
        ) : (
          <NotComputedNote />
        )}
      </section>
    </>
  );
}

function BehaviouralView({ data, targeted, excludePublic }) {
  // `targeted` mirrors the data.reform schema; the pipeline may omit some
  // result blocks for the targeted population, so every access is null-guarded.
  // `excludePublic` swaps in the *_excl_public scenarios (non-public only).
  const passThrough =
    (excludePublic
      ? (targeted ? targeted.pass_through_excl_public : data.reform.pass_through_excl_public)
      : (targeted ? targeted.pass_through : getPassThroughScenarios(data))) ?? [];
  const employment =
    (excludePublic
      ? (targeted ? targeted.employment_excl_public : data.reform.employment_excl_public)
      : (targeted ? targeted.employment : getEmploymentScenarios(data))) ?? [];
  const obr = data.official_stats.obr;
  const evidence = data.official_stats.elasticity_evidence;
  // Shown in the section copy when public-sector employers are excluded, so
  // the text matches the *_excl_public scenarios on screen.
  const publicScopeNote = excludePublic
    ? " Public-sector employers are excluded here: their employer NICs are paid by government to government, so exempting them nets out of the consolidated public finances; these scenarios cover non-public employees only."
    : "";
  const defaultScenario =
    passThrough.find(
      (s) => s.pass_through_rate === obr.medium_term_pass_through
    ) ||
    passThrough.find((s) => s.pass_through_rate > 0) ||
    passThrough[0] ||
    null;
  const [scenarioRate, setScenarioRate] = useState(
    defaultScenario ? defaultScenario.pass_through_rate : null
  );
  // Deciles are too granular for this chart; the targeted population
  // additionally drops quintiles (thin probability-weighted cells).
  const groupings = targeted ? ["quartiles"] : ["quintiles", "quartiles"];
  const [grouping, setGrouping] = useState(targeted ? "quartiles" : "quintiles");
  const scenario =
    passThrough.find((s) => s.pass_through_rate === scenarioRate) ||
    defaultScenario;

  if (scenario == null) {
    // The pipeline omitted pass-through runs for this population.
    return (
      <>
        <div className="pt-2">
          <SectionHeading size="lg" title="Wage pass-through" />
        </div>
        <section className="section-card">
          <NotComputedNote />
        </section>
        {SHOW_LABOUR_DEMAND &&
          (employment.length > 0 ? (
            <EmploymentSection
              data={data}
              evidence={evidence}
              employment={employment}
            />
          ) : (
            <>
              <div className="pt-2">
                <SectionHeading size="lg" title="Labour demand response" />
              </div>
              <section className="section-card">
                <NotComputedNote />
              </section>
            </>
          ))}
      </>
    );
  }

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
              {publicScopeNote}
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
          description={`Decomposition of the fiscal offset under the selected ${formatPct(scenario.pass_through_rate * 100, 0)} pass-through scenario. With zero pass-through no saving reaches workers' pay, so there is no offset or distributional effect to show; those results exist only for the scenarios with positive pass-through.`}
        />
        {scenario.pass_through_rate > 0 &&
          (scenario.offset_components_bn == null ? (
            <NotComputedNote />
          ) : (
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
                  <td>{formatBnFine(scenario.offset_components_bn.income_tax)}</td>
                </tr>
                <tr>
                  <td>Employee NICs on passed-through wages</td>
                  <td>
                    {formatBnFine(scenario.offset_components_bn.employee_nics)}
                  </td>
                </tr>
                <tr>
                  <td>Benefits saved</td>
                  <td>
                    {formatBnFine(scenario.offset_components_bn.benefits_saved)}
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
          ))}
      </section>

      {scenario.pass_through_rate > 0 && (
        <section className="section-card">
          <SectionHeading
            title="Average household net income change"
            description={`Average change in household net income in ${data.fiscal_year_label} under the ${formatPct(scenario.pass_through_rate * 100, 0)} pass-through scenario, across all households in each baseline income group (gainers and non-gainers alike).`}
          />
          {groupings.length > 1 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {groupings.map((g) => (
                <button
                  key={g}
                  className={`selector-chip compact capitalize ${grouping === g ? "active" : ""}`}
                  onClick={() => setGrouping(g)}
                >
                  {g}
                </button>
              ))}
            </div>
          )}
          {scenario.avg_change_by_group?.[grouping] == null ? (
            <NotComputedNote />
          ) : (
          <>
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
          </>
          )}
        </section>
      )}

      {SHOW_LABOUR_DEMAND &&
        (employment.length > 0 ? (
          <EmploymentSection
            data={data}
            evidence={evidence}
            employment={employment}
          />
        ) : (
          <>
            <div className="pt-2">
              <SectionHeading size="lg" title="Labour demand response" />
            </div>
            <section className="section-card">
              <NotComputedNote />
            </section>
          </>
        ))}
    </>
  );
}

function EmploymentSection({ data, evidence, employment }) {
  return (
    <>
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
              channels trade off against each other (money passed to wages
              cannot also cut employment costs), so this section and the
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
                  tip: "Employment gain applied to the count of employed 21-24-year-olds.",
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

// The targeted-population toggle exists only when the pipeline was run with
// LFS data; the JSON carries targeted: null (or omits it) otherwise.
const POPULATIONS = [
  { id: "all", label: "All employees aged 21-24" },
  { id: "neet", label: "Recent NEETs only" },
];

const EMPLOYERS = [
  { id: "all", label: "All employers" },
  { id: "exclude_public", label: "Exclude public-sector employers" },
];

function ToggleGroupLabel({ children }) {
  return (
    <span className="w-32 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">
      {children}
    </span>
  );
}

export default function ReformTab({ data }) {
  const targeted = data.targeted ?? null;
  // The employer-sector split exists only when the build ran on a dataset
  // with the employment_sector variable.
  const hasPublicSplit = (data.reform.static_excl_public ?? null) !== null;
  const [subTab, setSubTab] = useState("static");
  const [population, setPopulation] = useState("all");
  const [employer, setEmployer] = useState("all");
  const populationView = subTab === "static" || subTab === "behavioural";
  const useTargeted = targeted !== null && population === "neet";
  const activeTargeted = useTargeted ? targeted : null;
  const excludePublic = hasPublicSplit && employer === "exclude_public";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <ToggleGroupLabel>Analysis view</ToggleGroupLabel>
        <div className="flex flex-wrap items-center gap-2">
          {SUB_TABS.map((tab) => (
            <button
              key={tab.id}
              className={`toggle-button ${subTab === tab.id ? "active" : ""}`}
              onClick={() => setSubTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {targeted !== null && populationView && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <ToggleGroupLabel>Eligible workers</ToggleGroupLabel>
          <div className="flex flex-wrap items-center gap-2">
            {POPULATIONS.map((p) => (
              <button
                key={p.id}
                className={`toggle-button ${population === p.id ? "active" : ""}`}
                onClick={() => setPopulation(p.id)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {hasPublicSplit && populationView && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <ToggleGroupLabel>Employer scope</ToggleGroupLabel>
          <div className="flex flex-wrap items-center gap-2">
            {EMPLOYERS.map((e) => (
              <button
                key={e.id}
                className={`toggle-button ${employer === e.id ? "active" : ""}`}
                onClick={() => setEmployer(e.id)}
              >
                {e.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {subTab === "static" && (
        <StaticView
          key={`${useTargeted ? "targeted" : "all"}-${excludePublic ? "excl" : "all"}`}
          data={data}
          targeted={activeTargeted}
          excludePublic={excludePublic}
        />
      )}
      {subTab === "behavioural" && (
        <BehaviouralView
          key={`${useTargeted ? "targeted" : "all"}-${excludePublic ? "excl" : "all"}`}
          data={data}
          targeted={activeTargeted}
          excludePublic={excludePublic}
        />
      )}
    </div>
  );
}
