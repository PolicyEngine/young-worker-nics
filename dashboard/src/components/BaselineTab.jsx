"use client";

import { formatBn, formatCount, formatCurrency, formatPct } from "../lib/formatters";
import { getBaseline, getNicsParameters } from "../lib/dataHelpers";
import SectionHeading from "./SectionHeading";

export default function BaselineTab({ data }) {
  const baseline = getBaseline(data);
  const params = getNicsParameters(data);
  const neet = data.official_stats.neet;
  const hmrc = data.official_stats.hmrc_relief;
  const rti = data.official_stats.rti;
  const lfs = data.official_stats.lfs_employment;
  const ashe = data.official_stats.ashe_earnings;
  const reliefs = data.statutory_unmodelled;
  const recon = baseline.reconciliation;
  const bands = baseline.by_age_band;
  const band1820 = bands[0];
  const band2124 = bands[1];
  const relievedTotal = band1820.static_cost_bn + band2124.static_cost_bn;

  return (
    <div className="space-y-6">
      <section className="section-card">
        <SectionHeading
          title="Youth population by activity status"
          description="Every young person is in exactly one of three states: in education, in employment, or in neither (NEET). The NEET group is who this policy is for; the employed group is who the exemption is paid on. A student with a part-time job counts as both in education and in employment, and is never NEET. Model counts from the PolicyEngine UK enhanced FRS; the official column from the ONS."
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
              <td>Population</td>
              <td>{formatCount(recon.model_16_24.population)}</td>
              <td>{formatCount(recon.model_18_24.population)}</td>
              <td>
                ~
                <a
                  href={recon.official_16_24.source}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  {formatCount(recon.official_16_24.population_implied)}
                </a>
              </td>
            </tr>
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

      <section className="section-card">
        <SectionHeading
          title="Employer NICs paid on young workers"
          description={`Modelled employer NICs in ${data.fiscal_year_label} in the relieved band — earnings between the Secondary and Upper Secondary Thresholds, the only part the zero rate touches — by age band. The 18-20 amount is not actually paid in practice (under-21s are already exempt in law), so the 21-24 row is the reform's marginal static cost. ${data.age_band_note}`}
        />
        <table className="data-table">
          <thead>
            <tr>
              <th>Age band</th>
              <th>Employees</th>
              <th>Employer NICs in relieved band</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{band1820.group} (already exempt in law)</td>
              <td>{formatCount(band1820.n_employees)}</td>
              <td>{formatBn(band1820.static_cost_bn)}</td>
            </tr>
            <tr className="font-semibold">
              <td>{band2124.group} — the reform&apos;s marginal static cost</td>
              <td>{formatCount(band2124.n_employees)}</td>
              <td>{formatBn(data.reform.static.marginal_cost_bn)}</td>
            </tr>
            <tr>
              <td>All 18-24, relieved band</td>
              <td>{formatCount(baseline.n_employees_18_24)}</td>
              <td>{formatBn(relievedTotal)}</td>
            </tr>
            <tr>
              <td>All 18-24, total employer NICs (incl. earnings above the UST)</td>
              <td>{formatCount(baseline.n_employees_18_24)}</td>
              <td>{formatBn(baseline.employer_nics_18_24_bn)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="section-card">
        <SectionHeading
          title="Model versus official statistics"
          description="Cross-checks of model aggregates against published official figures."
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
              <td>Employees aged 18-24</td>
              <td>{formatCount(baseline.n_employees_18_24)}</td>
              <td>
                <a href={lfs.source} target="_blank" rel="noreferrer" className="underline">
                  {formatCount(lfs.employment_18_24)}
                </a>{" "}
                in employment, {lfs.period_label} (LFS)
              </td>
              <td>
                The LFS figure ({formatPct(lfs.employment_rate_18_24 * 100)} employment
                rate) includes the self-employed, whom the model&apos;s employee count
                excludes, so the model sits below it. HMRC{" "}
                <a href={rti.source} target="_blank" rel="noreferrer" className="underline">
                  RTI
                </a>
                &apos;s payrolled under-25 count fell{" "}
                {formatCount(Math.abs(rti.payrolled_under_25_change_yoy))} in the
                year to {rti.period_label}.
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
                among employed 21-24-year-olds — between ASHE&apos;s all-employee means
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
                ({neet.change_period_label}). The model proxy undershoots because the
                ONS measure is a point-in-time survey status that also counts training,
                while the proxy uses education status and annual employment income.
              </td>
            </tr>
          </tbody>
        </table>
      </section>

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
              extends this design to all employees aged 18-24.
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
    </div>
  );
}
