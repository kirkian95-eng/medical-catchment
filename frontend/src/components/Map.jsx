import React, { useRef, useCallback, useEffect, useState } from 'react';
import MapGL, { Source, Layer, NavigationControl, Popup } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import {
  catchmentFillColorExpr,
  catchmentFillOpacityExpr,
  govtShareToColor,
  formatPop,
  formatPct,
  formatMdi,
} from '../utils/colorScale';

const INITIAL_VIEW = {
  longitude: -97.5,
  latitude: 39.0,
  zoom: 4,
};

const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

export default function MapView({
  rankings,
  selectedHub,
  hubDetail,
  onSelectHub,
  onDeselectHub,
}) {
  const mapRef = useRef(null);
  const [catchmentData, setCatchmentData] = useState(null);
  const [interstateData, setInterstateData] = useState(null);
  const [hubPointsData, setHubPointsData] = useState(null);
  const [hospitalData, setHospitalData] = useState(null);
  const [hoverInfo, setHoverInfo] = useState(null);
  const [viewState, setViewState] = useState(INITIAL_VIEW);

  // Load catchment polygons and interstates on mount
  useEffect(() => {
    fetch(import.meta.env.BASE_URL + 'data/national_catchments.json')
      .then((r) => r.json())
      .then(setCatchmentData)
      .catch(() => {});
    fetch(import.meta.env.BASE_URL + 'data/interstates.geojson')
      .then((r) => r.json())
      .then(setInterstateData)
      .catch(() => {});
  }, []);

  // Build hub points GeoJSON from rankings
  useEffect(() => {
    if (!rankings.length) return;
    setHubPointsData({
      type: 'FeatureCollection',
      features: rankings.map((r) => ({
        type: 'Feature',
        properties: {
          cbsa_code: r.cbsa_code,
          name: r.cbsa_name,
          mdi: r.mdi,
          beds: r.total_beds,
          pop_catchment: r.pop_catchment,
          largest_hospital: r.largest_hospital,
        },
        geometry: {
          type: 'Point',
          coordinates: [r.hub_lon, r.hub_lat],
        },
      })),
    });
  }, [rankings]);

  // Build hospital markers for selected hub
  useEffect(() => {
    if (selectedHub && hubDetail) {
      setHospitalData({
        type: 'FeatureCollection',
        features: (hubDetail.hospitals || []).map((h) => ({
          type: 'Feature',
          properties: {
            name: h.name,
            beds: h.beds,
            type: h.type,
            ownership: h.ownership,
            govt_payer_share: h.govt_payer_share,
            color: govtShareToColor(h.govt_payer_share),
          },
          geometry: {
            type: 'Point',
            coordinates: [h.lon, h.lat],
          },
        })),
      });
    } else {
      setHospitalData(null);
    }
  }, [selectedHub, hubDetail]);

  // Fly to hub on selection
  useEffect(() => {
    if (!mapRef.current) return;

    if (selectedHub && hubDetail) {
      const [minLon, minLat, maxLon, maxLat] = hubDetail.bbox;
      mapRef.current.fitBounds(
        [[minLon, minLat], [maxLon, maxLat]],
        { padding: 60, duration: 1500 }
      );
    } else if (!selectedHub) {
      mapRef.current.flyTo({
        center: [INITIAL_VIEW.longitude, INITIAL_VIEW.latitude],
        zoom: INITIAL_VIEW.zoom,
        duration: 1200,
      });
    }
  }, [selectedHub, hubDetail]);

  const onHubClick = useCallback((e) => {
    if (e.features?.length) {
      onSelectHub(e.features[0].properties.cbsa_code);
    }
  }, [onSelectHub]);

  const onHubHover = useCallback((e) => {
    if (e.features?.length) {
      const f = e.features[0];
      setHoverInfo({
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        name: f.properties.name,
        mdi: f.properties.mdi,
        beds: f.properties.beds,
        pop_catchment: f.properties.pop_catchment,
        largest_hospital: f.properties.largest_hospital,
      });
    } else {
      setHoverInfo(null);
    }
  }, []);

  const isSelected = !!selectedHub;

  // Catchment fill opacity expression based on selection
  const catchmentOpacity = isSelected
    ? ['case', ['==', ['get', 'cbsa_code'], selectedHub], 0.35, 0.05]
    : catchmentFillOpacityExpr();

  const catchmentBorderOpacity = isSelected
    ? ['case', ['==', ['get', 'cbsa_code'], selectedHub], 0.6, 0.05]
    : ['interpolate', ['linear'], ['get', 'mdi'],
        0.0, 0.0,
        0.4, 0.0,
        0.5, 0.1,
        0.7, 0.25,
        1.0, 0.4,
      ];

  const catchmentBorderWidth = isSelected
    ? ['case', ['==', ['get', 'cbsa_code'], selectedHub], 2, 0.5]
    : 0.5;

  const hubCircleOpacity = isSelected
    ? ['case', ['==', ['get', 'cbsa_code'], selectedHub], 0, 0.2]
    : 0.9;

  return (
    <MapGL
      ref={mapRef}
      {...viewState}
      onMove={(e) => setViewState(e.viewState)}
      mapStyle={BASEMAP}
      style={{ width: '100%', height: '100%' }}
      maxZoom={12}
      minZoom={3}
      interactiveLayerIds={['hub-circles', 'hospital-circles']}
      onClick={onHubClick}
      onMouseMove={onHubHover}
      onMouseLeave={() => setHoverInfo(null)}
    >
      <NavigationControl position="top-right" />

      {/* Catchment polygons */}
      {catchmentData && (
        <Source id="catchments" type="geojson" data={catchmentData}>
          <Layer
            id="catchment-fill"
            type="fill"
            paint={{
              'fill-color': catchmentFillColorExpr(),
              'fill-opacity': catchmentOpacity,
            }}
          />
          <Layer
            id="catchment-border"
            type="line"
            paint={{
              'line-color': '#666',
              'line-width': catchmentBorderWidth,
              'line-opacity': catchmentBorderOpacity,
            }}
          />
        </Source>
      )}

      {/* Hub point markers */}
      {hubPointsData && (
        <Source id="hub-points" type="geojson" data={hubPointsData}>
          <Layer
            id="hub-circles"
            type="circle"
            paint={{
              'circle-radius': [
                'interpolate', ['linear'],
                ['sqrt', ['get', 'beds']],
                5, 2,      // 25 beds → 2px
                10, 3.5,   // 100 beds → 3.5px
                17, 5.5,   // ~300 beds → 5.5px
                26, 8,     // ~700 beds → 8px
                39, 12,    // ~1500 beds → 12px
                55, 18,    // ~3000 beds → 18px
              ],
              'circle-color': catchmentFillColorExpr(),
              'circle-stroke-color': '#fff',
              'circle-stroke-width': [
                'interpolate', ['linear'],
                ['sqrt', ['get', 'beds']],
                5, 0.5,
                20, 1,
                40, 1.5,
              ],
              'circle-opacity': isSelected ? hubCircleOpacity : [
                'interpolate', ['linear'], ['get', 'mdi'],
                0.0, 0.15,
                0.3, 0.35,
                0.5, 0.6,
                0.7, 0.85,
                1.0, 0.95,
              ],
            }}
          />
        </Source>
      )}

      {/* Interstate highways (visible in hub detail view for context) */}
      {interstateData && isSelected && (
        <Source id="interstates" type="geojson" data={interstateData}>
          <Layer
            id="interstate-lines"
            type="line"
            paint={{
              'line-color': '#94a3b8',
              'line-width': 1.2,
              'line-opacity': 0.5,
            }}
          />
        </Source>
      )}

      {/* Hospital markers (hub detail view) */}
      {hospitalData && (
        <Source id="hospital-markers" type="geojson" data={hospitalData}>
          <Layer
            id="hospital-circles"
            type="circle"
            paint={{
              'circle-radius': [
                'interpolate', ['linear'], ['get', 'beds'],
                25, 6,
                200, 10,
                500, 14,
                1000, 18,
              ],
              'circle-color': ['get', 'color'],
              'circle-stroke-color': '#fff',
              'circle-stroke-width': 2,
            }}
          />
        </Source>
      )}

      {/* Hover tooltip */}
      {hoverInfo && !isSelected && (
        <Popup
          longitude={hoverInfo.lng}
          latitude={hoverInfo.lat}
          closeButton={false}
          closeOnClick={false}
          anchor="bottom"
          offset={12}
        >
          <div className="text-sm">
            <div className="font-semibold text-stone-900">{hoverInfo.name}</div>
            <div className="text-stone-500 text-xs mt-1">
              MDI <span className="font-mono font-medium text-stone-800">{formatMdi(hoverInfo.mdi)}</span>
              {' '}&middot; {formatPop(hoverInfo.beds)} beds
              {' '}&middot; Catchment {formatPop(hoverInfo.pop_catchment)}
            </div>
            {hoverInfo.largest_hospital && (
              <div className="text-stone-400 text-xs mt-0.5">{hoverInfo.largest_hospital}</div>
            )}
          </div>
        </Popup>
      )}
    </MapGL>
  );
}
