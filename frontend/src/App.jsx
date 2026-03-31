import React from 'react';
import { useHubData } from './hooks/useHubData';
import MapView from './components/Map';
import HubRankingTable from './components/HubRankingTable';
import HubDetailPanel from './components/HubDetailPanel';
import Legend from './components/Legend';
import MethodologyPanel from './components/MethodologyPanel';

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

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-red-600 text-lg">Failed to load data: {error}</p>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-sidebar text-white px-6 py-4 flex-shrink-0">
        <h1 className="font-serif text-2xl tracking-tight">
          America's Hospital Towns
        </h1>
        <p className="text-stone-400 text-sm mt-0.5">
          Where the economy runs on Medicare
        </p>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar — show either ranking table OR hub detail, not both */}
        <div className="w-[400px] flex-shrink-0 bg-sidebar text-white flex flex-col overflow-hidden">
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

        {/* Map area */}
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

      {/* Methodology */}
      <MethodologyPanel />
    </div>
  );
}
