import React from 'react';
import { formatPop, formatPct, formatMdi, govtShareToColor } from '../utils/colorScale';

export default function HubDetailPanel({ hubDetail, loading, onClose }) {
  if (loading) {
    return (
      <div className="p-4 text-stone-400 text-sm border-t border-white/10">
        Loading hub details...
      </div>
    );
  }

  if (!hubDetail) return null;

  const s = hubDetail.summary || {};
  const hospitals = hubDetail.hospitals || [];

  // Auto-generate context sentence
  const hubName = hubDetail.cbsa_name || hubDetail.cbsa_code;
  const empShare = s.hospital_emp_share
    ? `${(s.hospital_emp_share * 100).toFixed(1)}% of the metro workforce`
    : '';
  const govtShare = s.avg_govt_payer_share
    ? `Government payers fund ${(s.avg_govt_payer_share * 100).toFixed(0)}% of inpatient hospital days.`
    : '';

  return (
    <div className="flex-1 overflow-y-auto sidebar-scroll">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-white/5 sticky top-0">
        <h3 className="font-serif text-base">
          {hubName}
          <span className="ml-2 font-mono text-xs text-stone-400">
            MDI {formatMdi(hubDetail.mdi)}
          </span>
        </h3>
        <button
          onClick={onClose}
          className="text-stone-400 hover:text-white text-xs px-2 py-1 rounded bg-white/5 hover:bg-white/10"
        >
          Back
        </button>
      </div>

      {/* Summary stats */}
      <div className="px-3 py-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <Stat label="Catchment Pop" value={formatPop(s.catchment_pop)} />
        <Stat label="65+ Share" value={formatPct(s.catchment_pct_65_plus)} />
        <Stat label="Catchment Radius" value={s.max_catchment_radius_miles ? `${Math.round(s.max_catchment_radius_miles)} mi` : 'N/A'} />
        <Stat label="Counties Served" value={s.num_counties} />
        <Stat label="Total Beds" value={s.total_beds?.toLocaleString()} />
        <Stat label="Hospital Employment" value={s.hospital_employment?.toLocaleString() || 'N/A'} />
      </div>

      {/* Context sentence */}
      {empShare && (
        <div className="px-3 pb-3">
          <p className="text-sm text-stone-300 italic leading-relaxed">
            {hubName}'s hospital systems
            {s.hospital_employment ? ` employ ${s.hospital_employment.toLocaleString()} people — ${empShare}` : ''}
            {s.num_counties ? ` and draw patients from a ${s.num_counties}-county catchment area` : ''}
            {s.catchment_pop ? `, serving a population of ${formatPop(s.catchment_pop)}` : ''}.{' '}
            {govtShare}
          </p>
        </div>
      )}

      {/* Hospital inventory */}
      {hospitals.length > 0 && (
        <div className="px-3 pb-3">
          <h4 className="text-xs font-semibold text-stone-400 mb-2 uppercase tracking-wider">
            Hospitals
          </h4>
          <div className="space-y-1.5">
            {hospitals.map((h) => (
              <div
                key={h.facility_id}
                className="bg-white/5 rounded px-2 py-1.5 text-xs"
              >
                <div className="flex items-center gap-2">
                  <div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ background: govtShareToColor(h.govt_payer_share) }}
                  />
                  <span className="font-medium truncate">{h.name}</span>
                </div>
                <div className="flex gap-3 mt-1 text-stone-400 ml-4">
                  <span className="font-mono">{h.beds} beds</span>
                  <span>{h.type?.replace('Hospitals', '').trim()}</span>
                  <span className="font-mono">
                    {formatPct(h.govt_payer_share)} govt
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-stone-500 text-[10px] uppercase tracking-wider">{label}</div>
      <div className="font-mono text-sm text-white mt-0.5">{value ?? 'N/A'}</div>
    </div>
  );
}
