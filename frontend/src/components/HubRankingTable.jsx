import React, { useState, useMemo } from 'react';
import { FixedSizeList as List } from 'react-window';
import { formatMdi, formatPop } from '../utils/colorScale';

const POP_BANDS = [
  { label: 'Focus Hubs (<2M)', filter: (r) => r.is_focus_hub },
  { label: 'All MSAs', filter: () => true },
  { label: 'Large Metros (2M+)', filter: (r) => !r.is_focus_hub },
  { label: 'Under 100K', filter: (r) => r.pop_msa < 100_000 },
  { label: '100K–500K', filter: (r) => r.pop_msa >= 100_000 && r.pop_msa < 500_000 },
  { label: '500K–2M', filter: (r) => r.pop_msa >= 500_000 && r.pop_msa < 2_000_000 },
  { label: '2M+', filter: (r) => r.pop_msa >= 2_000_000 },
];

const SORT_OPTIONS = [
  { key: 'mdi', label: 'MDI Score', desc: true },
  { key: 'pop_catchment', label: 'Catchment Pop', desc: true },
  { key: 'total_beds', label: 'Total Beds', desc: true },
  { key: 'component_a_hospital_emp_share', label: 'Emp Share', desc: true },
  { key: 'component_b_govt_payer_share', label: 'Govt Payer', desc: true },
  { key: 'pop_msa', label: 'MSA Pop', desc: true },
];

export default function HubRankingTable({ rankings, loading, selectedHub, onSelect }) {
  const [search, setSearch] = useState('');
  const [popBand, setPopBand] = useState(0);
  const [sortKey, setSortKey] = useState('mdi');

  const filtered = useMemo(() => {
    let items = [...rankings];

    // Search filter
    if (search) {
      const q = search.toLowerCase();
      items = items.filter(
        (r) =>
          (r.cbsa_name || '').toLowerCase().includes(q) ||
          (r.largest_hospital || '').toLowerCase().includes(q)
      );
    }

    // Pop/type filter
    const band = POP_BANDS[popBand];
    items = items.filter(band.filter);

    // Sort
    const opt = SORT_OPTIONS.find((o) => o.key === sortKey) || SORT_OPTIONS[0];
    items.sort((a, b) => {
      const av = a[opt.key] ?? 0;
      const bv = b[opt.key] ?? 0;
      return opt.desc ? bv - av : av - bv;
    });

    return items;
  }, [rankings, search, popBand, sortKey]);

  const Row = ({ index, style }) => {
    const r = filtered[index];
    const isSelected = r.cbsa_code === selectedHub;
    const mdiBar = Math.round(r.mdi * 100);

    return (
      <div
        style={style}
        className={`px-3 py-2 cursor-pointer border-b border-white/5 transition-colors ${
          isSelected
            ? 'bg-white/15'
            : 'hover:bg-white/5'
        }`}
        onClick={() => onSelect(r.cbsa_code)}
      >
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-xs text-stone-500 w-6 text-right flex-shrink-0">
            {r.mdi_rank}
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">
              {r.cbsa_name || r.cbsa_code}
            </div>
            <div className="flex items-center gap-3 mt-1">
              {/* MDI bar */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${mdiBar}%`,
                      background: `linear-gradient(90deg, #feb24c, #d73027)`,
                    }}
                  />
                </div>
                <span className="font-mono text-xs text-stone-300">
                  {formatMdi(r.mdi)}
                </span>
              </div>
              {/* Stats */}
              <span className="text-[11px] text-stone-400 font-mono">
                {formatPop(r.total_beds)}b
              </span>
              <span className="text-[11px] text-stone-400 font-mono">
                {formatPop(r.pop_catchment)}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Controls */}
      <div className="px-3 py-3 space-y-2 flex-shrink-0 border-b border-white/10">
        <input
          type="text"
          placeholder="Search hubs..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-white/10 text-white text-sm px-3 py-1.5 rounded border border-white/10 placeholder:text-stone-500 focus:outline-none focus:border-white/30"
        />
        <div className="flex gap-2">
          <select
            value={popBand}
            onChange={(e) => setPopBand(Number(e.target.value))}
            className="flex-1 bg-white/10 text-white text-xs px-2 py-1 rounded border border-white/10 focus:outline-none"
          >
            {POP_BANDS.map((b, i) => (
              <option key={i} value={i} className="bg-stone-800">
                {b.label}
              </option>
            ))}
          </select>
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value)}
            className="flex-1 bg-white/10 text-white text-xs px-2 py-1 rounded border border-white/10 focus:outline-none"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.key} value={o.key} className="bg-stone-800">
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="text-xs text-stone-500">
          {filtered.length} hubs
        </div>
      </div>

      {/* List */}
      <div className="flex-1 sidebar-scroll">
        {loading ? (
          <div className="p-4 text-stone-400 text-sm">Loading hubs...</div>
        ) : (
          <List
            height={600}
            itemCount={filtered.length}
            itemSize={64}
            width="100%"
          >
            {Row}
          </List>
        )}
      </div>
    </div>
  );
}
