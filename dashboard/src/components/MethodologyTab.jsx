"use client";

import { useEffect } from "react";
import { formatCurrency, formatPct } from "../lib/formatters";
import SectionHeading from "./SectionHeading";

const METHOD_LABELS = {
  static: "Static cost",
  pass_through: "Wage pass-through and fiscal offsets",
  poverty: "Poverty impact",
  distributional: "Distributional impact",
  // employment: hidden with the labour demand response section; restore the
  // label here when that section returns to the reform tab.
  // reform_object: hidden — internal build-time cross-check, not a result.
};
// Rendered in its own box below the grid, not as a grid entry.
const TARGETED_METHOD_KEY = "targeted_population";

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
      {data.methods[TARGETED_METHOD_KEY] && (
        <section
          className="section-card scroll-mt-24"
          id={`method-${TARGETED_METHOD_KEY}`}
        >
          <SectionHeading
            title="Targeted population imputation"
            description="The method behind the reform tab's recent-NEET population assumption."
          />
          <p className="text-sm leading-6 text-slate-600">
            {data.methods[TARGETED_METHOD_KEY]}
          </p>
        </section>
      )}

      <section className="section-card">
        <SectionHeading
          title="Computation methods"
          description="Static microsimulation on the PolicyEngine UK enhanced Family Resources Survey, with scenario-based behavioural layers. Statutory parameters are read from the PolicyEngine parameter tree, never hard-coded. Each note below is written by the analysis pipeline alongside the result it describes."
        />
        <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
          {Object.entries(data.methods)
            .filter(([key]) => METHOD_LABELS[key])
            .map(([key, text]) => (
              <div key={key} id={`method-${key}`} className="scroll-mt-24">
                <h3 className="text-sm font-semibold text-slate-800">
                  {METHOD_LABELS[key]}
                </h3>
                <p className="mt-1 text-sm leading-6 text-slate-600">{text}</p>
              </div>
            ))}
        </div>
      </section>

      <section className="section-card">
        <SectionHeading title="Wage pass-through assumption" />
        <p className="text-sm leading-6 text-slate-600">
          The <a href={obr.source} target="_blank" rel="noreferrer" className="underline">OBR</a>{" "}
          assumed the {obr.nics_rise_year} employer NICs <em>rise</em> would be
          passed to workers as lower real wages:{" "}
          {formatPct(obr.initial_pass_through * 100, 0)} in {obr.initial_year_label},{" "}
          {formatPct(obr.medium_term_pass_through * 100, 0)} from{" "}
          {obr.medium_term_year_label}. But the{" "}
          <a href={saez.url} target="_blank" rel="noreferrer" className="underline">
            evidence
          </a>{" "}
          on <em>age-targeted</em> cuts (Sweden&apos;s under-26 cut; Saez,
          Schoefer &amp; Seim 2019) found approximately zero pass-through to the
          targeted workers&apos; own wages: pay-equity norms and the binding
          National Living Wage make age-specific pay rises unlikely. We
          therefore present{" "}
          {formatPct(settings.pass_through_scenarios[0] * 100, 0)} as the central
          case with{" "}
          {settings.pass_through_scenarios
            .slice(1)
            .map((r) => formatPct(r * 100, 0))
            .join(" and ")}{" "}
          as sensitivities.
        </p>
      </section>

      <section className="section-card scroll-mt-24" id="model-omissions">
        <SectionHeading title="Model limitations" />
        <ul className="list-disc space-y-1 pl-6 text-sm leading-6 text-slate-600">
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
            {formatCurrency(employmentAllowance.value)} already pay nothing on
            these workers, so the static cost is overstated (the FRS has no
            employer-side data).
          </li>
          <li>
            General-equilibrium and substitution effects (e.g. hiring shifted
            away from workers aged 25+ just above the cutoff).
          </li>
          <li>
            Corporation-tax offset on the unpassed share: where employers keep
            the saving, taxable profits rise, so net costs are overstated at
            low pass-through rates.
          </li>
          <li>
            Apprentices under 25 are already exempt in law (category H) but
            invisible in the FRS, so no adjustment is made for them.
          </li>
          <li>Public-sector recycling of the cost within government.</li>
          <li>Single-year-of-age detail: {data.age_band_note}</li>
        </ul>
      </section>

    </div>
  );
}
