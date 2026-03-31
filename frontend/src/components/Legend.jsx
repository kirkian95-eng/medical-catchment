import React from 'react';
import { govtShareToColor } from '../utils/colorScale';

const MDI_STOPS = [
  { value: 0.0, color: '#ffffcc', label: '0.0' },
  { value: 0.2, color: '#ffeda0', label: '0.2' },
  { value: 0.4, color: '#feb24c', label: '0.4' },
  { value: 0.6, color: '#f03b20', label: '0.6' },
  { value: 0.8, color: '#bd0026', label: '0.8' },
  { value: 1.0, color: '#800026', label: '1.0' },
];

const GOVT_STOPS = [
  { share: 0.3, label: '<40%' },
  { share: 0.45, label: '40–50%' },
  { share: 0.55, label: '50–60%' },
  { share: 0.7, label: '>60%' },
];

export default function Legend({ selectedHub }) {
  return (
    <div className="absolute bottom-4 left-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg px-4 py-3 text-xs max-w-[200px]">
      {!selectedHub ? (
        <>
          <div className="font-semibold text-stone-700 mb-2">
            Medical Dependence Index
          </div>
          <div className="flex h-3 rounded-sm overflow-hidden mb-1">
            {MDI_STOPS.map((s, i) => (
              <div
                key={i}
                className="flex-1"
                style={{ background: s.color }}
              />
            ))}
          </div>
          <div className="flex justify-between text-stone-500 text-[10px]">
            <span>Low</span>
            <span>High</span>
          </div>
          <div className="mt-2 text-[10px] text-stone-400">
            Circle size = hospital beds
          </div>
        </>
      ) : (
        <>
          <div className="font-semibold text-stone-700 mb-2">
            Govt Payer Share
          </div>
          <div className="space-y-1">
            {GOVT_STOPS.map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ background: govtShareToColor(s.share) }}
                />
                <span className="text-stone-600">{s.label}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-[10px] text-stone-400">
            Marker size = bed count
          </div>
        </>
      )}
    </div>
  );
}
