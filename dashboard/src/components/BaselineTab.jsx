"use client";

import { formatBn, formatCount, formatCurrency, formatPct } from "../lib/formatters";
import { getBaseline, getNicsParameters } from "../lib/dataHelpers";
import SectionHeading from "./SectionHeading";

export default function BaselineTab({ data }) {
  const baseline = getBaseline(data);
  const params = getNicsParameters(data);
  const neet = data.official_stats.neet;
  const hmrc = data.official_stats.hmrc_relief;
  const ashe = data.official_stats.ashe_earnings;
  const reliefs = data.statutory_unmodelled;
  const recon = baseline.reconciliation;

  return (
    <div className="space-y-6">
      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="The youth labour market"
          description="Who the policy is for, and who it is paid on. The NEET group is the policy's target; the employed group is where the exemption flows. The gap between the two is why much of a blanket hiring subsidy goes to employment that would exist anyway, and why the reform tab also prices a targeted variant covering only employees who were recently NEET."
        />
      </div>

      <section className="section-card">
        <SectionHeading
          title="Youth population by activity status"
          description={`Every young person is in exactly one of three states: in education, in employment, or in neither (NEET). A student with a part-time job counts as both in education and in employment, and is never NEET. Model counts from PolicyEngine UK; the official column from the ONS.${
            data.targeted?.entrant_share != null
              ? ` These states churn: in the LFS five-quarter panels, ${formatPct(data.targeted.entrant_share * 100, 1)} of employed 21-24-year-olds were NEET at some point in the previous year, the entrant share behind the reform tab's targeted variant.`
              : ""
          }`}
        />
        <table className="data-table">
          <thead>
            <tr>
              <th>State</th>
              <th>Model, 16-24</th>
              <th>Model, 18-24</th>
              <th>Official, 16-24</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>In education</td>
              <td>{formatCount(recon.model_16_24.in_education)}</td>
              <td>{formatCount(recon.model_18_24.in_education)}</td>
              <td>—</td>
            </tr>
            <tr>
              <td>In employment (incl. working students)</td>
              <td>{formatCount(recon.model_16_24.in_employment)}</td>
              <td>{formatCount(recon.model_18_24.in_employment)}</td>
              <td>—</td>
            </tr>
            <tr>
              <td>In neither (NEET)</td>
              <td>
                {formatCount(recon.model_16_24.neet_proxy)} (
                {formatPct(recon.model_16_24.neet_proxy_rate * 100)})
              </td>
              <td>
                {formatCount(recon.model_18_24.neet_proxy)} (
                {formatPct(recon.model_18_24.neet_proxy_rate * 100)})
              </td>
              <td>
                <a
                  href={recon.official_16_24.source}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  {formatCount(recon.official_16_24.neet_level)}
                </a>{" "}
                ({formatPct(recon.official_16_24.neet_rate * 100)})
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      {baseline.public_private_employment && (
        <section className="section-card">
          <SectionHeading
            title="Public and private sector employment"
            description="Whether a worker's main job is in the public sector (NHS, state schools, councils, civil service, armed forces) or the private sector, from the survey main-job sector. This matters for the reform: employer NICs on a public-sector job are paid by government to government, so exempting them nets out of the consolidated public finances — the reform tab's 'exclude public-sector employers' toggle removes them from the cost. Young workers skew heavily private."
          />
          <table className="data-table">
            <thead>
              <tr>
                <th>Measure</th>
                <th>Model</th>
                <th>Official</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Public-sector employees (all ages)</td>
                <td>{formatCount(baseline.public_private_employment.n_public_all_employees)}</td>
                <td>
                  ~
                  <a
                    href={data.official_stats.public_sector_employment.source}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {formatCount(data.official_stats.public_sector_employment.total_uk)}
                  </a>{" "}
                  (ONS PSE, {data.official_stats.public_sector_employment.period_label})
                </td>
              </tr>
              <tr>
                <td>Public share of all employees</td>
                <td>
                  {formatPct(
                    (baseline.public_private_employment.n_public_all_employees /
                      (baseline.public_private_employment.n_public_all_employees +
                        baseline.public_private_employment.n_private_all_employees)) *
                      100,
                    1,
                  )}
                </td>
                <td>
                  ~
                  <a
                    href={data.official_stats.public_sector_employment.source}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {formatPct(
                      data.official_stats.public_sector_employment.share_of_total_employment * 100,
                      1,
                    )}
                  </a>{" "}
                  (ONS)
                </td>
              </tr>
              <tr>
                <td>Public-sector employees, 18-24</td>
                <td>{formatCount(baseline.public_private_employment.n_public_18_24)}</td>
                <td>—</td>
              </tr>
              <tr>
                <td>Public share among 18-24 employees</td>
                <td>{formatPct(baseline.public_private_employment.public_share_18_24 * 100, 1)}</td>
                <td>—</td>
              </tr>
            </tbody>
          </table>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            The model&apos;s all-ages public-sector total sits close to the ONS Public
            Sector Employment headcount. ONS does not publish a public/private split
            for 18-24-year-olds specifically; the model&apos;s low youth public share
            reflects that NHS, teaching and civil-service roles skew older.
          </p>
        </section>
      )}

      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="Employer NICs on young workers today"
          description="The statutory parameters as they stand, and the modelled employer NICs at stake in the band the zero rate would touch."
        />
      </div>

      <section className="section-card">
        <SectionHeading
          title="NICs rates and thresholds"
          description={
            <>
              Statutory parameters read from the PolicyEngine UK parameter tree for{" "}
              {data.fiscal_year_label}; nothing here is typed into the analysis by
              hand. Employers pay NICs at the rate below on each employee&apos;s
              earnings above the Secondary Threshold (annualised from the statutory
              weekly figure, hence not a round number). The existing zero rate for
              under-21s (
              <a
                href={reliefs.under_21_relief.url}
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                category M
              </a>
              ) switches that charge off between the Secondary and Upper Secondary
              Thresholds; the full rate still applies above the UST. The reform
              extends this design either to all employees aged 18-24, or, in the
              targeted variant, only to 21-24-year-olds who were NEET within the
              past year.
            </>
          }
        />
        <table className="data-table">
          <tbody>
            <tr>
              <td>Employer (secondary Class 1) rate</td>
              <td>{formatPct(params.employer_rate * 100)}</td>
            </tr>
            <tr>
              <td>Secondary Threshold (annual)</td>
              <td>{formatCurrency(params.secondary_threshold_annual)}</td>
            </tr>
            <tr>
              <td>Upper Secondary Threshold (annual)</td>
              <td>{formatCurrency(params.upper_secondary_threshold_annual)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <div className="pt-2">
        <SectionHeading
          size="lg"
          title="Reconciliation with official statistics"
          description="Cross-checks of model aggregates against published ONS and HMRC figures, with the definitional gaps explained."
        />
      </div>

      <section className="section-card">
        <SectionHeading
          title="Model versus official statistics"
          description="Each row pairs a model quantity with the nearest published figure."
        />
        <table className="data-table">
          <thead>
            <tr>
              <th>Quantity</th>
              <th>This model</th>
              <th>Official figure</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Employer NICs relieved band, ages 18-20</td>
              <td>
                {formatBn(baseline.static_cost_18_20_bn)} ({data.fiscal_year_label}{" "}
                params)
              </td>
              <td>
                <a href={hmrc.source} target="_blank" rel="noreferrer" className="underline">
                  {formatBn(hmrc.under_21_relief_forecast_2025_26_bn)}
                </a>{" "}
                HMRC forecast {hmrc.forecast_period_label}
              </td>
              <td>
                HMRC&apos;s {hmrc.forecast_period_label} forecast for the under-21
                relief is the first scored at the post-April-2025 parameters, so it is
                directly comparable. It covers all under-21s (including 16-17s) where
                the model band is 18-20 only, but counts only relief actually claimed
                through payroll category letters, and uses{" "}
                {hmrc.forecast_period_label} earnings. Outturn at the old parameters
                was {formatBn(hmrc.under_21_relief_cost_2024_25_bn)} in{" "}
                {hmrc.outturn_period_label}.
              </td>
            </tr>
            <tr>
              <td>Average pay of employed 21-24s</td>
              <td>
                ≈
                {formatCurrency(
                  params.secondary_threshold_annual +
                    data.reform.static.avg_saving_per_employee / params.employer_rate
                )}{" "}
                mean (implied)
              </td>
              <td>
                {formatCurrency(ashe.mean_annual_pay_18_21)} (18-21) /{" "}
                {formatCurrency(ashe.mean_annual_pay_22_29)} (22-29) mean,{" "}
                {ashe.period_label} (
                <a href={ashe.source} target="_blank" rel="noreferrer" className="underline">
                  ASHE
                </a>
                )
              </td>
              <td>
                The model&apos;s average NICs saving of{" "}
                {formatCurrency(data.reform.static.avg_saving_per_employee)} implies
                mean NICable pay of about{" "}
                {formatCurrency(
                  params.secondary_threshold_annual +
                    data.reform.static.avg_saving_per_employee / params.employer_rate
                )}{" "}
                among employed 21-24-year-olds, between ASHE&apos;s all-employee means
                for the 18-21 and 22-29 bands that straddle it.
              </td>
            </tr>
            <tr>
              <td>NEET 16-24</td>
              <td>
                {formatCount(recon.model_16_24.neet_proxy)} (
                {formatPct(recon.model_16_24.neet_proxy_rate * 100)}) proxy
              </td>
              <td>
                <a href={neet.source} target="_blank" rel="noreferrer" className="underline">
                  {formatCount(neet.level)}
                </a>{" "}
                / {formatPct(neet.rate * 100)}, {neet.period_label} (ONS)
              </td>
              <td>
                ONS level rose {formatCount(neet.year_on_year_change)} on a year earlier
                ({neet.change_period_label}).
              </td>
            </tr>
          </tbody>
        </table>
      </section>

    </div>
  );
}
