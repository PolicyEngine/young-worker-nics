"use client";

import { useEffect } from "react";
import { formatCurrency, formatPct } from "../lib/formatters";
import SectionHeading from "./SectionHeading";

const METHOD_LABELS = {
  static: "Static cost",
  pass_through: "Wage pass-through and fiscal offsets",
  poverty: "Poverty impact",
  distributional: "Distributional impact",
  employment: "Employment response",
  reform_object: "Reform implementation",
  reconciliation: "Population reconciliation",
};

export default function MethodologyTab({ data }) {
  // Analysis sections link here with /?tab=methodology#method-<key>; the tab
  // mounts after navigation, so the browser's native hash scroll has already
  // missed and we replay it.
  useEffect(() => {
    const hash = window.location.hash;
    if (hash) {
      document.getElementById(hash.slice(1))?.scrollIntoView();
    }
  }, []);

  const settings = data.settings;
  const obr = data.official_stats.obr;
  const saez = data.assumptions.pass_through_scenarios[0];
  const employmentAllowance = data.statutory_unmodelled.employment_allowance;

  return (
    <div className="space-y-6">
      <section className="section-card">
        <SectionHeading
          title="How the model works"
          description="Static microsimulation with scenario-based behavioural layers."
        />
        <ol className="list-decimal space-y-2 pl-6 text-slate-700">
          <li>
            Load the PolicyEngine UK baseline (enhanced Family Resources Survey)
            via the <code>policyengine.py</code> managed bundle.
          </li>
          <li>
            Read statutory parameters (employer rate, Secondary Threshold, Upper
            Earnings Limit as the Upper Secondary Threshold proxy) from the
            PolicyEngine parameter tree — never hard-coded.
          </li>
          <li>
            Compute the employer NICs forgone for each employed 21-24-year-old:
            the rate times NICable earnings between the Secondary Threshold and
            the Upper Secondary Threshold. Under-21s are already zero-rated, so
            the marginal cost covers employed 21-24-year-olds.
          </li>
          <li>
            For each wage pass-through scenario, boost the employment income of
            employed 21-24-year-olds and re-run the full microsimulation, so
            income tax, employee NICs and benefit withdrawal are computed
            exactly; apply labour demand elasticity scenarios on the
            employment-cost wedge.
          </li>
        </ol>
      </section>

      <section className="section-card">
        <SectionHeading
          title="How each result is computed"
          description="Method explainers written by the analysis pipeline alongside the results, reproduced verbatim. Each section of the analysis links to its entry here."
        />
        <dl className="space-y-4">
          {Object.entries(data.methods).map(([key, text]) => (
            <div key={key} id={`method-${key}`} className="scroll-mt-24">
              <dt className="eyebrow text-slate-500">{METHOD_LABELS[key]}</dt>
              <dd className="mt-1 text-sm leading-6 text-slate-700">{text}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="section-card">
        <SectionHeading
          title="Assumption: wage pass-through"
          description="Whose pocket does the saving land in?"
        />
        <p className="mb-3 text-slate-700">
          The OBR assumed the {obr.nics_rise_year} employer NICs <em>rise</em>{" "}
          would be passed to workers via lower real wages —{" "}
          {formatPct(obr.initial_pass_through * 100, 0)} in {obr.initial_year_label},
          rising to{" "}
          <a href={obr.source} target="_blank" rel="noreferrer" className="underline">
            {formatPct(obr.medium_term_pass_through * 100, 0)} from{" "}
            {obr.medium_term_year_label}
          </a>
          . But the evidence on <em>age-targeted</em> payroll tax cuts —{" "}
          <a href={saez.url} target="_blank" rel="noreferrer" className="underline">
            Sweden&apos;s under-26 cut (Saez, Schoefer &amp; Seim 2019)
          </a>{" "}
          — found approximately zero pass-through to the targeted workers&apos;
          own wages: firms kept the windfall and responded on the employment
          margin instead. Pay-equity norms and the binding National Living Wage
          make age-specific pay rises unlikely. We therefore present{" "}
          {formatPct(settings.pass_through_scenarios[0] * 100, 0)} as the central
          case with{" "}
          {settings.pass_through_scenarios
            .slice(1)
            .map((r) => formatPct(r * 100, 0))
            .join(" and ")}{" "}
          as sensitivities.
        </p>
      </section>

      <section className="section-card">
        <SectionHeading title="What the model captures" />
        <ul className="list-disc space-y-1 pl-6 text-slate-700">
          <li>Statutory employer NICs arithmetic, capped at the Upper Secondary Threshold</li>
          <li>Restriction to the 21-24 marginal population (under-21s are already exempt)</li>
          <li>Tax-benefit clawback of passed-through wage gains</li>
          <li>Scenario-based labour demand responses with literature-supported elasticities</li>
          <li>
            Exact tax-benefit interactions for the single-worker calculator,
            computed through the unified <code>policyengine.py</code> household API
          </li>
        </ul>
      </section>

      <section className="section-card scroll-mt-24" id="model-omissions">
        <SectionHeading title="What the model omits" />
        <ul className="list-disc space-y-1 pl-6 text-slate-700">
          <li>
            <a
              href={employmentAllowance.url}
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              Employment Allowance
            </a>{" "}
            interactions: small employers with secondary NICs below{" "}
            {formatCurrency(employmentAllowance.value)} already pay nothing
            on these workers, so the static cost is overstated (the FRS has no
            employer-side data).
          </li>
          <li>
            General-equilibrium and substitution effects (e.g. hiring shifted away
            from workers aged 25+ just above the cutoff).
          </li>
          <li>
            Corporation-tax offset on the unpassed share: where the employer keeps
            the NICs saving, taxable profits rise and part of the cost would flow
            back to the Exchequer as corporation tax. This offset is not yet
            modelled, so net costs are overstated at low pass-through rates.
          </li>
          <li>
            Apprentices under 25 are already exempt in law (category H), but
            the FRS contains no apprentice identifier, so we skip them
            entirely — no adjustment is made anywhere in the results.
          </li>
          <li>Public-sector recycling of the cost within government.</li>
          <li>
            Single-year-of-age detail: {data.age_band_note}
          </li>
        </ul>
      </section>

      <section className="section-card">
        <SectionHeading
          title="Assumptions registry"
          description="Every non-PolicyEngine number in the analysis, with its source."
        />
        <table className="data-table">
          <thead>
            <tr>
              <th>Assumption</th>
              <th>Value</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries({
              "Calculator annual rent": data.assumptions.calculator_annual_rent,
              ...Object.fromEntries(
                data.assumptions.pass_through_scenarios.map((s) => [
                  `Pass-through ${formatPct(s.value * 100, 0)}`,
                  s,
                ])
              ),
              ...Object.fromEntries(
                Object.entries(data.assumptions.demand_elasticities).map(([k, s]) => [
                  `Demand elasticity (${k})`,
                  s,
                ])
              ),
            }).map(([label, source]) => (
              <tr key={label}>
                <td>{label}</td>
                <td>{source.value}</td>
                <td>
                  <a href={source.url} target="_blank" rel="noreferrer" className="underline">
                    {source.description}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
