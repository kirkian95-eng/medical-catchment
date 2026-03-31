import React, { useMemo } from 'react';
import { formatPop, formatPct, formatMdi } from '../utils/colorScale';

export default function WhitepaperNarrative({ rankings }) {
  const stats = useMemo(() => {
    if (!rankings.length) return null;
    const focus = rankings.filter((r) => r.is_focus_hub);
    const focusBeds = focus.reduce((s, r) => s + (r.total_beds || 0), 0);
    const totalCatchment = focus.reduce((s, r) => s + (r.pop_catchment || 0), 0);
    const top10 = focus.slice(0, 10);

    return {
      totalHubs: rankings.length,
      focusHubs: focus.length,
      focusBeds,
      totalCatchment,
      top10,
      highGovt: focus.filter((r) => r.component_b_govt_payer_share > 0.55).length,
    };
  }, [rankings]);

  return (
    <>
      {/* Masthead */}
      <nav className="sticky top-0 z-50 bg-paper/95 backdrop-blur border-b border-stone-200 px-6 py-3">
        <div className="max-w-[1100px] mx-auto flex items-center justify-between">
          <span className="text-[11px] font-mono tracking-[0.25em] text-stone-500 uppercase font-medium">
            Medical Catchment Project
          </span>
          <span className="text-[11px] font-mono text-stone-400">March 2026</span>
        </div>
      </nav>

      {/* Floating skip-to-map button */}
      <a
        href="#explore"
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 bg-sidebar text-white rounded-full shadow-lg hover:bg-stone-700 transition-colors text-sm font-medium"
      >
        Skip to map <span>&darr;</span>
      </a>

      {/* Hero */}
      <header className="max-w-[1100px] mx-auto px-6 pt-16 pb-10">
        <p className="text-[11px] font-mono tracking-[0.2em] text-stone-400 uppercase mb-6">
          Healthcare Employment Analysis &middot; 2023 Data
        </p>
        <h1 className="font-serif text-[clamp(2.5rem,5vw,4.5rem)] leading-[1.05] tracking-tight text-stone-900 mb-6">
          America's<br />
          <em className="italic">Hospital Towns</em>
        </h1>
        <p className="text-xl leading-relaxed text-stone-500 max-w-[680px] mb-10">
          In hundreds of American towns, the hospital isn't just the largest employer
          — it <em>is</em> the economy. A conduit for federal Medicare and Medicaid dollars
          into the local labor market. This analysis maps where those towns are, how
          dependent they are, and who they serve.
        </p>

        {/* Metadata bar */}
        <div className="border-t border-b border-stone-200 py-4 grid grid-cols-3 gap-6 text-sm">
          <div>
            <span className="font-semibold text-stone-700">Scope:</span>{' '}
            <span className="text-stone-500">{stats?.totalHubs || '—'} MSAs, contiguous US</span>
          </div>
          <div>
            <span className="font-semibold text-stone-700">Index:</span>{' '}
            <span className="text-stone-500">3-component Medical Dependence Index</span>
          </div>
          <div>
            <span className="font-semibold text-stone-700">Sources:</span>{' '}
            <span className="text-stone-500">CMS Cost Reports, BLS QCEW, Census ACS</span>
          </div>
        </div>
      </header>

      {/* Thesis — one tight paragraph + callout */}
      <section className="max-w-[1100px] mx-auto px-6 pb-12">
        <SectionLabel>The Thesis</SectionLabel>
        <Prose>
          Medicare and Medicaid pay for 60–70% of inpatient days at the average community hospital.
          In a metro like Dallas, that makes the hospital one employer among thousands. In a town of
          50,000, a 400-bed medical center employing 3,000 people at above-average wages{' '}
          <em>is</em> the economy. When CMS adjusts reimbursement rates, when Medicare Advantage
          penetration increases, when rural hospitals consolidate — these towns feel it first.
        </Prose>
        <Callout>
          A high MDI score doesn't mean the hospital is good or bad. It means the local economy
          would be devastated if it closed.
        </Callout>
      </section>

      {/* Key Findings — stat cards + table */}
      <section className="max-w-[1100px] mx-auto px-6 pb-12">
        <SectionLabel>Key Findings</SectionLabel>

        {stats && (
          <>
            <div className="grid grid-cols-4 gap-4 mb-10">
              <StatCard label="Focus Hubs" sublabel="MSAs under 2M pop" value={stats.focusHubs} />
              <StatCard label="Hospital Beds" sublabel="in focus hubs" value={stats.focusBeds.toLocaleString()} />
              <StatCard label="Catchment Pop" sublabel="served by focus hubs" value={formatPop(stats.totalCatchment)} />
              <StatCard label="High Govt Share" sublabel=">55% govt-funded days" value={stats.highGovt} />
            </div>

            <h3 className="font-serif text-xl text-stone-800 mb-4">
              Top 10 by Dependence Index
            </h3>
            <div className="border border-stone-200 rounded-lg overflow-hidden mb-6">
              <table className="w-full text-sm">
                <thead className="bg-stone-100 text-stone-500 text-[11px] font-mono uppercase tracking-wider">
                  <tr>
                    <th className="text-left px-4 py-3">#</th>
                    <th className="text-left px-4 py-3">MSA</th>
                    <th className="text-right px-4 py-3">MDI</th>
                    <th className="text-right px-4 py-3">Beds</th>
                    <th className="text-right px-4 py-3">Emp %</th>
                    <th className="text-right px-4 py-3">Govt %</th>
                    <th className="text-right px-4 py-3">Catchment</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top10.map((r, i) => (
                    <tr key={r.cbsa_code} className={i % 2 === 0 ? 'bg-white' : 'bg-stone-50'}>
                      <td className="px-4 py-2.5 font-mono text-stone-400">{r.mdi_rank}</td>
                      <td className="px-4 py-2.5 font-medium text-stone-800">{r.cbsa_name}</td>
                      <td className="px-4 py-2.5 text-right font-mono font-semibold text-accent">{formatMdi(r.mdi)}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{r.total_beds.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{formatPct(r.component_a_hospital_emp_share)}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{formatPct(r.component_b_govt_payer_share)}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{formatPop(r.pop_catchment)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {/* The Index — component cards only, minimal prose */}
      <section className="max-w-[1100px] mx-auto px-6 pb-12">
        <SectionLabel>The Index</SectionLabel>

        <div className="grid grid-cols-3 gap-6 mb-6">
          <ComponentCard
            weight="40%" letter="A" title="Employment Intensity" color="bg-red-700"
            description="Hospital FTEs as a share of total local employment. Sourced from CMS cost reports to bypass BLS suppression."
          />
          <ComponentCard
            weight="30%" letter="B" title="Government Payer Share" color="bg-amber-600"
            description="Share of inpatient days funded by Medicare and Medicaid, from actual cost report patient day data."
          />
          <ComponentCard
            weight="30%" letter="C" title="Payroll Dominance" color="bg-stone-700"
            description="Hospital payroll as a share of total local payroll. Captures the wage premium hospitals carry."
          />
        </div>

        <div className="bg-stone-100 rounded-lg px-6 py-4 font-mono text-sm text-stone-700">
          MDI = 0.40 &times; A + 0.30 &times; B + 0.30 &times; C
          <span className="text-stone-400 ml-4">(each normalized 0–1 using 95th percentile scaling)</span>
        </div>
      </section>
    </>
  );
}

/* ---- Sub-components ---- */

function SectionLabel({ children }) {
  return (
    <div className="flex items-center gap-4 mb-6">
      <span className="text-[11px] font-mono tracking-[0.2em] text-stone-400 uppercase whitespace-nowrap">
        {children}
      </span>
      <div className="flex-1 h-px bg-accent/30" />
    </div>
  );
}

function Prose({ children }) {
  return (
    <p className="text-lg leading-[1.75] text-stone-700 mb-5 max-w-[780px]">
      {children}
    </p>
  );
}

function Callout({ children }) {
  return (
    <blockquote className="border-l-4 border-accent bg-stone-100/60 rounded-r-lg px-6 py-4 my-6 text-[15px] leading-relaxed text-stone-600 max-w-[780px]">
      {children}
    </blockquote>
  );
}

function StatCard({ label, sublabel, value }) {
  return (
    <div className="border border-stone-200 rounded-lg px-5 py-4">
      <p className="text-[10px] font-mono tracking-[0.15em] text-stone-400 uppercase mb-1">{label}</p>
      <p className="text-3xl font-serif text-stone-900 mb-1">{value}</p>
      <p className="text-xs text-stone-400">{sublabel}</p>
    </div>
  );
}

function ComponentCard({ weight, letter, title, description, color }) {
  return (
    <div className="border border-stone-200 rounded-lg overflow-hidden">
      <div className={`${color} text-white px-4 py-2 flex items-center justify-between text-xs`}>
        <span className="font-mono font-bold">Component {letter}</span>
        <span className="font-mono">{weight}</span>
      </div>
      <div className="px-4 py-3">
        <h4 className="font-serif text-base font-semibold text-stone-800 mb-1.5">{title}</h4>
        <p className="text-sm text-stone-500 leading-relaxed">{description}</p>
      </div>
    </div>
  );
}
