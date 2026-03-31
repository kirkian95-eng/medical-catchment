import React, { useMemo } from 'react';
import { formatPop, formatPct, formatMdi } from '../utils/colorScale';

export default function WhitepaperNarrative({ rankings, onExploreMap }) {
  const stats = useMemo(() => {
    if (!rankings.length) return null;
    const focus = rankings.filter((r) => r.is_focus_hub);
    const totalBeds = rankings.reduce((s, r) => s + (r.total_beds || 0), 0);
    const focusBeds = focus.reduce((s, r) => s + (r.total_beds || 0), 0);
    const totalCatchment = focus.reduce((s, r) => s + (r.pop_catchment || 0), 0);
    const top10 = focus.slice(0, 10);
    const medianMdi = focus.length
      ? focus[Math.floor(focus.length / 2)].mdi
      : 0;

    // Top examples for narrative
    const topByBeds = [...focus].sort((a, b) => b.total_beds - a.total_beds).slice(0, 5);
    const topByEmpShare = [...focus].sort(
      (a, b) => b.component_a_hospital_emp_share - a.component_a_hospital_emp_share
    ).slice(0, 5);

    return {
      totalHubs: rankings.length,
      focusHubs: focus.length,
      metroCount: rankings.length - focus.length,
      totalBeds,
      focusBeds,
      totalCatchment,
      top10,
      medianMdi,
      topByBeds,
      topByEmpShare,
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

      {/* Hero */}
      <header className="max-w-[1100px] mx-auto px-6 pt-16 pb-12">
        <p className="text-[11px] font-mono tracking-[0.2em] text-stone-400 uppercase mb-6">
          Healthcare Employment Analysis &middot; 2023 Data
        </p>
        <h1 className="font-serif text-[clamp(2.5rem,5vw,4.5rem)] leading-[1.05] tracking-tight text-stone-900 mb-6">
          America's<br />
          <em className="italic">Hospital Towns</em>
        </h1>
        <p className="text-xl leading-relaxed text-stone-500 max-w-[680px] mb-10">
          In hundreds of American towns too small to have diversified economies, the hospital
          system functions as the primary economic engine — a conduit for federal Medicare and
          Medicaid dollars into the local labor market. This analysis identifies those towns,
          quantifies the dependence, and maps who they serve.
        </p>

        {/* Metadata bar */}
        <div className="border-t border-b border-stone-200 py-4 grid grid-cols-3 gap-6 text-sm">
          <div>
            <span className="font-semibold text-stone-700">Scope:</span>{' '}
            <span className="text-stone-500">{stats?.totalHubs || '—'} MSAs, contiguous US</span>
          </div>
          <div>
            <span className="font-semibold text-stone-700">Index:</span>{' '}
            <span className="text-stone-500">3-component Medical Dependence Index (MDI)</span>
          </div>
          <div>
            <span className="font-semibold text-stone-700">Sources:</span>{' '}
            <span className="text-stone-500">CMS Cost Reports, BLS QCEW, Census ACS</span>
          </div>
        </div>
      </header>

      {/* Section: The Thesis */}
      <section className="max-w-[1100px] mx-auto px-6 pb-16">
        <SectionLabel>The Thesis</SectionLabel>

        <Prose>
          The American hospital is, in economic terms, a federal transfer mechanism. Medicare
          and Medicaid — programs funded by federal and state tax revenue — pay for roughly
          60–70% of inpatient days at the average community hospital. The hospital converts
          those payments into local wages: nurses, technicians, administrators, food service
          workers, maintenance staff. In a large metropolitan area like Dallas or Chicago, this
          is one employer among thousands. But in a town of 50,000, a 400-bed regional medical
          center employing 3,000 people at above-average wages isn't just the largest employer
          — it <em>is</em> the economy.
        </Prose>
        <Prose>
          This project asks a simple question: <strong>where are those towns, and how dependent
          are they?</strong> We compute a Medical Dependence Index for every metropolitan and
          micropolitan statistical area in the contiguous United States, measuring three things:
          how large a share of local employment the hospital represents, how much of its patient
          load is government-funded, and how much of the local payroll flows through the hospital
          system.
        </Prose>

        <Callout>
          The MDI is not a quality metric. A high score does not mean the hospital is good or
          bad. It means the local economy would be devastated if the hospital closed — because
          nothing else of comparable scale exists to replace those jobs, those wages, and that
          federal revenue stream.
        </Callout>
      </section>

      {/* Section: Key Findings */}
      <section className="max-w-[1100px] mx-auto px-6 pb-16">
        <SectionLabel>Key Findings</SectionLabel>

        {stats && (
          <>
            {/* Stat cards */}
            <div className="grid grid-cols-4 gap-4 mb-12">
              <StatCard label="Focus Hubs" sublabel="MSAs under 2M pop" value={stats.focusHubs} />
              <StatCard label="Hospital Beds" sublabel="in focus hubs" value={stats.focusBeds.toLocaleString()} />
              <StatCard label="Catchment Pop" sublabel="served by focus hubs" value={formatPop(stats.totalCatchment)} />
              <StatCard label="High Govt Share" sublabel=">55% govt-funded days" value={stats.highGovt} />
            </div>

            {/* Top 10 table */}
            <h3 className="font-serif text-xl text-stone-800 mb-4">
              Top 10 Medical Hub Towns by Dependence Index
            </h3>
            <div className="border border-stone-200 rounded-lg overflow-hidden mb-8">
              <table className="w-full text-sm">
                <thead className="bg-stone-100 text-stone-500 text-[11px] font-mono uppercase tracking-wider">
                  <tr>
                    <th className="text-left px-4 py-3">Rank</th>
                    <th className="text-left px-4 py-3">MSA</th>
                    <th className="text-right px-4 py-3">MDI</th>
                    <th className="text-right px-4 py-3">Beds</th>
                    <th className="text-right px-4 py-3">Hosp Emp %</th>
                    <th className="text-right px-4 py-3">Govt Payer %</th>
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

      {/* Section: The Components */}
      <section className="max-w-[1100px] mx-auto px-6 pb-16">
        <SectionLabel>The Index</SectionLabel>

        <Prose>
          The Medical Dependence Index is a weighted composite of three normalized scores,
          each measuring a different dimension of hospital economic dominance:
        </Prose>

        <div className="grid grid-cols-3 gap-6 my-10">
          <ComponentCard
            weight="40%"
            letter="A"
            title="Employment Intensity"
            description="Hospital employees (NAICS 622) as a share of total local employment. Sourced from CMS cost report FTEs — not BLS, which suppresses data for exactly the single-employer counties this tool is designed to find."
            color="bg-red-700"
          />
          <ComponentCard
            weight="30%"
            letter="B"
            title="Government Payer Share"
            description="Share of inpatient days funded by Medicare and Medicaid, weighted by bed count. Computed from actual inpatient days in CMS cost reports, not estimates."
            color="bg-amber-600"
          />
          <ComponentCard
            weight="30%"
            letter="C"
            title="Payroll Dominance"
            description="Hospital payroll as a share of total local payroll. Hospital jobs pay above-average wages — a hospital accounting for 8% of jobs but 12% of payroll tells a different story."
            color="bg-stone-700"
          />
        </div>

        <Prose>
          Each component is normalized to [0, 1] using the minimum and 95th percentile across
          focus hubs (MSAs under 2 million). Large metros are included on the map but excluded
          from normalization so their diversified economies don't compress the scale.
        </Prose>

        <div className="bg-stone-100 rounded-lg px-6 py-5 my-8 font-mono text-sm text-stone-700">
          MDI = 0.40 &times; A<sub>normalized</sub> + 0.30 &times; B<sub>normalized</sub> + 0.30 &times; C<sub>normalized</sub>
        </div>
      </section>

      {/* Section: Catchments */}
      <section className="max-w-[1100px] mx-auto px-6 pb-16">
        <SectionLabel>Catchment Areas</SectionLabel>

        <Prose>
          Each hub's catchment represents the surrounding population that is geographically
          closest to that hub's hospitals, adjusted for hospital size. Larger hospitals draw
          patients from farther away — the effective distance to a hospital is divided by the
          log of its bed count, so a 500-bed regional medical center "pulls" from roughly 3.6
          times the effective distance of a 25-bed Critical Access Hospital.
        </Prose>

        <Prose>
          Every county in the contiguous United States is assigned to exactly one hub. In rural
          areas, a single hub may serve a 20-county, 100-mile radius catchment. In urban
          corridors, catchments are compact and dense. The catchment population — not the MSA
          population — is the relevant denominator for understanding a hospital's reach.
        </Prose>

        <Callout>
          The map below assigns all 3,109 contiguous US counties to their nearest medical hub.
          Catchment boundaries are geometric approximations based on straight-line distance —
          real patient flow follows highway access, referral networks, and insurance contracts.
          Drive-time isochrones would be more precise but are a V2 enhancement.
        </Callout>
      </section>

      {/* Section: The Pattern */}
      <section className="max-w-[1100px] mx-auto px-6 pb-16">
        <SectionLabel>The Pattern</SectionLabel>

        <Prose>
          The map reveals a clear geographic signature. The American interior — the Great
          Plains, the Upper Midwest, Appalachia, the rural South, the Mountain West — lights
          up with medical dependence. The coasts are quieter: large, diversified metros
          dominate, and hospitals are one employer among many.
        </Prose>
        <Prose>
          This is not a coincidence. The towns with the highest MDI scores share structural
          features: they are regional referral centers for surrounding rural populations,
          they are too small to have attracted other large employers, and their demographics
          skew older (more Medicare-eligible). The hospital didn't become dominant by accident
          — it became dominant because nothing else scaled.
        </Prose>
        <Prose>
          The policy implication is significant. These are the towns where a hospital closure
          wouldn't just reduce healthcare access — it would eliminate the largest employer, the
          highest-paying jobs, and the primary mechanism by which federal dollars enter the
          local economy. When CMS adjusts reimbursement rates, when Medicare Advantage
          penetration increases, when rural hospitals consolidate — these towns feel it first.
        </Prose>

        {/* CTA to map */}
        <div className="mt-10 flex justify-center">
          <a
            href="#explore"
            className="inline-flex items-center gap-2 px-6 py-3 bg-sidebar text-white rounded-lg hover:bg-stone-700 transition-colors text-sm font-medium"
          >
            Explore the map
            <span className="text-lg">&darr;</span>
          </a>
        </div>
      </section>
    </>
  );
}

/* ---- Reusable sub-components ---- */

function SectionLabel({ children }) {
  return (
    <div className="flex items-center gap-4 mb-8">
      <span className="text-[11px] font-mono tracking-[0.2em] text-stone-400 uppercase whitespace-nowrap">
        {children}
      </span>
      <div className="flex-1 h-px bg-accent/30" />
    </div>
  );
}

function Prose({ children }) {
  return (
    <p className="text-lg leading-[1.75] text-stone-700 mb-6 max-w-[780px]">
      {children}
    </p>
  );
}

function Callout({ children }) {
  return (
    <blockquote className="border-l-4 border-accent bg-stone-100/60 rounded-r-lg px-6 py-5 my-8 text-[15px] leading-relaxed text-stone-600 max-w-[780px]">
      <strong className="text-stone-800">Why this matters: </strong>
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
      <div className="px-4 py-4">
        <h4 className="font-serif text-base font-semibold text-stone-800 mb-2">{title}</h4>
        <p className="text-sm text-stone-500 leading-relaxed">{description}</p>
      </div>
    </div>
  );
}
