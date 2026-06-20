"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import BaselineTab from "../src/components/BaselineTab";
import MethodologyTab from "../src/components/MethodologyTab";
import ReformTab from "../src/components/ReformTab";

const TAB_OPTIONS = [
  { id: "reform", label: "Young-worker NICs exemption" },
  { id: "baseline", label: "Youth labour market baseline" },
  { id: "methodology", label: "Methodology" },
];

function getInitialTab(tabParam) {
  if (TAB_OPTIONS.some((tab) => tab.id === tabParam)) {
    return tabParam;
  }
  return "reform";
}

function TabLink({ onSelect, children }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="font-semibold text-[color:var(--pe-color-primary-600)] underline decoration-1 underline-offset-2 transition-opacity hover:opacity-80"
    >
      {children}
    </button>
  );
}

function Dashboard() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState(() => getInitialTab(searchParams.get("tab")));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const tabParam = searchParams.get("tab");
    setActiveTab(getInitialTab(tabParam));
  }, [searchParams]);

  useEffect(() => {
    async function loadData() {
      try {
        const response = await fetch("/data/young_worker_nics_results.json");
        if (!response.ok) {
          throw new Error("young_worker_nics_results.json not found; run the pipeline first");
        }
        const json = await response.json();
        setData(json);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, []);

  function handleTabChange(tab) {
    setActiveTab(tab);
    if (tab === "reform") {
      router.replace("/", { scroll: false });
      return;
    }
    router.replace(`/?tab=${tab}`, { scroll: false });
  }

  return (
    <div className="app-shell min-h-screen">
      <header className="title-row">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between px-6 py-4 md:px-8">
          <h1>Employer NICs exemption for young workers analysis</h1>
        </div>
      </header>

      <main className="relative z-[1] mx-auto max-w-[1400px] px-6 py-10 md:px-8 md:py-12">
        <div className="animate-[fadeIn_0.4s_ease-out]">
          <p className="mb-3 text-[1.05rem] leading-relaxed text-slate-600">
            This dashboard uses{" "}
            <a href="https://policyengine.org" target="_blank" rel="noreferrer" className="underline">
              PolicyEngine
            </a>{" "}
            UK&apos;s microsimulation model to estimate the fiscal cost and employment
            effects of extending the employer NICs zero rate, which already
            covers{" "}
            {data ? (
              <a
                href={data.statutory_unmodelled.under_21_relief.url}
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                under-21s
              </a>
            ) : (
              "under-21s"
            )}{" "}
            and apprentices under 25, up to the Upper Secondary Threshold
            {data ? `, for fiscal year ${data.fiscal_year_label}` : ""}, in two
            variants: to all employees aged 18 to 24, or targeted only at
            employees aged 21 to 24 who were NEET within the past year. The
            policy context is set out in Alan Milburn&apos;s Young People and
            Work interim{" "}
            <a
              href="https://www.gov.uk/government/publications/young-people-and-work-interim-report/young-people-and-work-interim-report"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              review
            </a>{" "}
            (DWP, May 2026), which found nearly one million 16-24-year-olds, one
            in eight, not in education, employment or training. The{" "}
            <TabLink onSelect={() => handleTabChange("reform")}>
              Young-worker NICs exemption
            </TabLink>{" "}
            tab shows the static cost of the reform and the behavioural results:
            wage pass-through simulations and poverty and distributional impacts.
            It can switch between the full 21-24 population and a targeted
            population of employees who were recently NEET. The{" "}
            <TabLink onSelect={() => handleTabChange("baseline")}>
              Youth labour market baseline
            </TabLink>{" "}
            tab reconciles the model with official statistics on NEETs and employer
            NICs. The{" "}
            <TabLink onSelect={() => handleTabChange("methodology")}>
              Methodology
            </TabLink>{" "}
            tab explains how every result is computed, with sources for every
            assumption.
          </p>
        </div>

        <div className="mb-8 mt-8 flex w-fit flex-wrap border-b-2 border-slate-200">
          {TAB_OPTIONS.map((tab) => (
            <button
              key={tab.id}
              className={`tab-button ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => handleTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {error && (
          <p className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            Error: {error}
          </p>
        )}
        {loading && !error && (
          <p className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
            Loading data...
          </p>
        )}

        {!loading && !error && data && (
          <>
            {activeTab === "reform" && <ReformTab data={data} />}
            {activeTab === "baseline" && <BaselineTab data={data} />}
            {activeTab === "methodology" && <MethodologyTab data={data} />}
          </>
        )}

        <footer className="mt-12 border-t border-slate-200 pt-8 text-center text-sm text-slate-500">
          <p>
            Replication code:{" "}
            <a
              href="https://github.com/PolicyEngine/young-worker-nics"
              target="_blank"
              rel="noreferrer"
            >
              PolicyEngine/young-worker-nics
            </a>
            {data?.package_versions
              ? `, run on ${Object.entries(data.package_versions)
                  .map(
                    ([name, version]) =>
                      `${name === "policyengine" ? "policyengine.py" : name} ${version}`
                  )
                  .join(" and ")}`
              : ""}
            .
          </p>
        </footer>
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense
      fallback={<p className="p-12 text-center text-slate-500">Loading...</p>}
    >
      <Dashboard />
    </Suspense>
  );
}
