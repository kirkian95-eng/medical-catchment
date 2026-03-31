import { useState, useEffect, useCallback, useRef } from 'react';

const DATA_BASE = import.meta.env.BASE_URL + 'data';

/**
 * Hook to load hub rankings (national view) and per-hub detail (drill-down).
 */
export function useHubData() {
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedHub, setSelectedHub] = useState(null);
  const [hubDetail, setHubDetail] = useState(null);
  const [hubDetailLoading, setHubDetailLoading] = useState(false);
  const hubCache = useRef({});

  // Load rankings on mount
  useEffect(() => {
    fetch(`${DATA_BASE}/hub_rankings.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setRankings(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Load per-hub detail on selection
  const selectHub = useCallback(
    (cbsaCode) => {
      if (cbsaCode === selectedHub) {
        // Deselect
        setSelectedHub(null);
        setHubDetail(null);
        return;
      }

      setSelectedHub(cbsaCode);
      setHubDetailLoading(true);

      if (hubCache.current[cbsaCode]) {
        setHubDetail(hubCache.current[cbsaCode]);
        setHubDetailLoading(false);
        return;
      }

      fetch(`${DATA_BASE}/hubs/${cbsaCode}.json`)
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then((data) => {
          hubCache.current[cbsaCode] = data;
          setHubDetail(data);
          setHubDetailLoading(false);
        })
        .catch(() => {
          setHubDetail(null);
          setHubDetailLoading(false);
        });
    },
    [selectedHub]
  );

  const deselectHub = useCallback(() => {
    setSelectedHub(null);
    setHubDetail(null);
  }, []);

  return {
    rankings,
    loading,
    error,
    selectedHub,
    hubDetail,
    hubDetailLoading,
    selectHub,
    deselectHub,
  };
}
