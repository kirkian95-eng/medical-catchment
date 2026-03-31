import React, { useState } from 'react';
import { useHubData } from './hooks/useHubData';
import MapView from './components/Map';
import HubRankingTable from './components/HubRankingTable';
import HubDetailPanel from './components/HubDetailPanel';
import Legend from './components/Legend';
import WhitepaperNarrative from './components/WhitepaperNarrative';

export default function App() {
  const {
    rankings,
    loading,
    error,
    selectedHub,
    hubDetail,
    hubDetailLoading,
    selectHub,
    deselectHub,
  } = useHubData();

  const [showMap, setShowMap] = useState(false);

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-paper">
        <p className="text-red-600 text-lg">Failed to load data: {error}</p>
      </div>
    );
  }

  return (
    <div className="bg-paper text-stone-800 min-h-screen">
      {/* Scrolling narrative */}
      <WhitepaperNarrative
        rankings={rankings}
        onExploreMap={() => setShowMap(true)}
      />

      {/* Full interactive map section */}
      <section id="explore" className="relative">
        <div className="max-w-[1100px] mx-auto px-6 pt-12 pb-6">
          <div className="flex items-center gap-4 mb-8">
            <span className="text-[11px] font-mono tracking-[0.2em] text-stone-400 uppercase">
              Interactive Explorer
            </span>
            <div className="flex-1 h-px bg-accent/30" />
          </div>
          <p className="font-serif text-lg text-stone-600 mb-6 max-w-[700px]">
            Click any hub to drill into its catchment area, hospital inventory, and employment data.
            Use the sidebar to search, filter, and sort.
          </p>
        </div>

        <div className="h-[85vh] flex border-t border-stone-200">
          {/* Sidebar */}
          <div className="w-[380px] flex-shrink-0 bg-sidebar text-white flex flex-col overflow-hidden">
            {selectedHub ? (
              <HubDetailPanel
                hubDetail={hubDetail}
                loading={hubDetailLoading}
                onClose={deselectHub}
              />
            ) : (
              <HubRankingTable
                rankings={rankings}
                loading={loading}
                selectedHub={selectedHub}
                onSelect={selectHub}
              />
            )}
          </div>

          {/* Map */}
          <div className="flex-1 relative">
            <MapView
              rankings={rankings}
              selectedHub={selectedHub}
              hubDetail={hubDetail}
              onSelectHub={selectHub}
              onDeselectHub={deselectHub}
            />
            <Legend selectedHub={selectedHub} />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-sidebar text-stone-400 py-12 px-6">
        <div className="max-w-[1100px] mx-auto">
          <div className="flex items-center gap-4 mb-6">
            <span className="text-[11px] font-mono tracking-[0.2em] uppercase text-stone-500">
              Sources &amp; Methodology
            </span>
            <div className="flex-1 h-px bg-stone-700" />
          </div>
          <div className="grid grid-cols-2 gap-8 text-sm leading-relaxed">
            <div>
              <p className="text-stone-500 mb-3 font-medium">Data Sources</p>
              <ul className="space-y-1 text-stone-400">
                <li>CMS Hospital Provider Cost Report (FY 2023)</li>
                <li>CMS Medicare Inpatient Hospitals by Provider (DY 2023)</li>
                <li>CMS Provider of Services File (Q4 2025)</li>
                <li>BLS Quarterly Census of Employment &amp; Wages (2023)</li>
                <li>Census ACS 5-Year Estimates (2022)</li>
                <li>Census TIGER/Line County Boundaries (2022)</li>
                <li>OMB CBSA Delineation File (2023)</li>
              </ul>
            </div>
            <div>
              <p className="text-stone-500 mb-3 font-medium">Limitations</p>
              <ul className="space-y-1 text-stone-400">
                <li>BLS suppresses employment for single-employer counties; recovered via cost report FTEs</li>
                <li>Catchment boundaries are geometric approximations, not actual patient flow</li>
                <li>Cost report data lags 1–2 years; some hospitals file late</li>
                <li>VA and psychiatric facilities excluded</li>
                <li>Payer mix estimated from inpatient days, not revenue</li>
              </ul>
            </div>
          </div>
          <div className="mt-8 pt-6 border-t border-stone-700 text-xs text-stone-500">
            Built with CMS, BLS, and Census public data. Map powered by MapLibre GL JS.
          </div>
        </div>
      </footer>
    </div>
  );
}
