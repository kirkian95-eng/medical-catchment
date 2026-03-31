import React, { useState } from 'react';

const SECTIONS = [
  {
    title: 'What is the Medical Dependence Index?',
    body: `The MDI measures how much a local economy depends on its hospital system as an economic engine. A high score means the hospital is a dominant employer, a large share of its patients are covered by Medicare and Medicaid (government programs), and hospital payroll represents an outsized share of the local economy.`,
  },
  {
    title: 'Why this matters',
    body: `In hundreds of American towns, the hospital is the largest or second-largest employer. Its revenue comes primarily from Medicare and Medicaid — federal and state programs that transfer dollars from the national tax base into the local economy. These towns function as medical catchment areas for surrounding rural populations that lack local specialty care. Understanding where these hubs are, who they serve, and how dependent they are on government healthcare spending is critical for economic development, housing investment, and healthcare policy.`,
  },
  {
    title: 'The Components',
    body: `The MDI is a weighted composite of three normalized scores:

Component A — Hospital Employment Intensity (40%): Hospital employment (NAICS 622) as a share of total county employment. National median is ~3-4%; medical hub towns range 6-12%+.

Component B — Government Payer Intensity (30%): The bed-weighted average share of inpatient days funded by Medicare and Medicaid across all hospitals in the MSA.

Component C — Hospital Payroll Dominance (30%): Hospital payroll as a share of total county payroll, capturing not just headcount but economic weight — hospitals often pay above-average wages.

MDI = 0.40×A + 0.30×B + 0.30×C, with each component normalized to [0,1] using min and 95th percentile scaling.`,
  },
  {
    title: 'Catchment Areas',
    body: `Each hub's catchment represents the population that is geographically closest to that hub's hospitals, weighted for hospital size. Larger hospitals draw patients from farther away — the effective distance to a hospital is divided by log₂(beds), so a 500-bed hospital "pulls" from ~3.6× the effective distance of a 25-bed facility. Every county in the contiguous US is assigned to exactly one hub based on this weighted distance.`,
  },
  {
    title: "What's excluded and why",
    body: `Metropolitan areas with populations over 2 million are excluded. These metros (New York, Los Angeles, Chicago, Dallas-Fort Worth, etc.) have diversified economies where hospitals, while important, are not structurally dominant employers. This tool focuses on the smaller metros and micropolitan areas where hospital dependence is a defining economic characteristic. Alaska, Hawaii, and territories are also excluded.`,
  },
  {
    title: 'Data sources',
    body: `• CMS Hospital General Information — hospital inventory, beds, type, ownership, coordinates
• CMS Medicare Inpatient Utilization — Medicare discharges and payments by hospital
• BLS Quarterly Census of Employment and Wages (QCEW) — county-level employment by industry
• Census ACS 5-Year Estimates (2022) — population and age distribution by county
• Census TIGER/Line (2022) — county boundary geometries
• Census CBSA Delineation File (2023) — metropolitan/micropolitan area definitions`,
  },
  {
    title: 'Limitations',
    body: `• BLS suppresses employment data for small counties where a single employer would be identifiable — this hits exactly the counties with the most dominant hospitals. Suppressed values are estimated using a beds-to-FTE ratio.
• CMS cost report data lags 1-2 years. Medicare utilization is used as a proxy for full payer mix where cost reports are unavailable.
• Catchment boundaries are geometric approximations — real patient flow follows referral networks, insurance networks, and highway access, not just straight-line distance.
• VA hospitals and psychiatric facilities are excluded, though they contribute to local employment.
• Multi-campus hospital systems may be counted as separate facilities.`,
  },
];

export default function MethodologyPanel() {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(null);

  return (
    <div className="bg-stone-100 border-t border-stone-200">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-6 py-2.5 flex items-center justify-between text-sm text-stone-600 hover:text-stone-800"
      >
        <span className="font-medium">Methodology & Data Sources</span>
        <span className="text-lg">{open ? '\u2212' : '+'}</span>
      </button>

      {open && (
        <div className="px-6 pb-6 max-h-[50vh] overflow-y-auto">
          <div className="max-w-3xl space-y-1">
            {SECTIONS.map((s, i) => (
              <div key={i} className="border-b border-stone-200 last:border-0">
                <button
                  onClick={() => setExpanded(expanded === i ? null : i)}
                  className="w-full py-3 flex items-center justify-between text-sm text-left"
                >
                  <span className="font-medium text-stone-700">{s.title}</span>
                  <span className="text-stone-400 ml-4">
                    {expanded === i ? '\u2212' : '+'}
                  </span>
                </button>
                {expanded === i && (
                  <div className="pb-4 text-sm text-stone-600 leading-relaxed whitespace-pre-line">
                    {s.body}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
