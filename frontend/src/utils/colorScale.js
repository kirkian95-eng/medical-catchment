import { interpolateYlOrRd } from 'd3-scale-chromatic';
import { scaleLinear } from 'd3-scale';
import { format } from 'd3-format';

/**
 * MDI → fill color for catchment areas and hub points.
 * Warm sequential: pale yellow → deep orange → dark red.
 */
export function mdiToColor(mdi) {
  // Offset to avoid near-white for low values
  return interpolateYlOrRd(mdi * 0.85 + 0.15);
}

/**
 * MDI → fill opacity for catchment polygons.
 */
export function mdiToOpacity(mdi) {
  return 0.15 + mdi * 0.45; // range: 0.15 – 0.60
}

/**
 * Government payer share → hospital marker color (hub detail view).
 */
export function govtShareToColor(share) {
  if (share < 0.40) return '#4575b4';
  if (share < 0.50) return '#fee090';
  if (share < 0.60) return '#fc8d59';
  return '#d73027';
}

/**
 * Beds → circle radius in pixels for hub markers.
 */
export function bedsToRadius(beds) {
  return Math.max(4, Math.log2(beds + 1) * 1.8);
}

/**
 * Format large numbers abbreviated: 485000 → "485K"
 */
export function formatPop(n) {
  if (n == null) return 'N/A';
  if (n >= 1_000_000) return format('.2s')(n).replace('M', 'M');
  if (n >= 1_000) return format('.3s')(n).replace('k', 'K');
  return format(',')(n);
}

/**
 * Format percentage: 0.1723 → "17.2%"
 */
export function formatPct(n) {
  if (n == null) return 'N/A';
  return (n * 100).toFixed(1) + '%';
}

/**
 * Format MDI score: 0.9234 → "0.92"
 */
export function formatMdi(n) {
  if (n == null) return 'N/A';
  return n.toFixed(2);
}

/**
 * Build MapLibre data-driven style expression for catchment fill color.
 */
export function catchmentFillColorExpr() {
  // Stepped color based on MDI property
  return [
    'interpolate',
    ['linear'],
    ['get', 'mdi'],
    0.0, '#ffffcc',
    0.2, '#ffeda0',
    0.4, '#feb24c',
    0.6, '#f03b20',
    0.8, '#bd0026',
    1.0, '#800026',
  ];
}

/**
 * Build MapLibre data-driven style expression for catchment fill opacity.
 * Low-MDI areas fade to near-invisible so the map doesn't look universally dependent.
 */
export function catchmentFillOpacityExpr() {
  return [
    'interpolate',
    ['linear'],
    ['get', 'mdi'],
    0.0, 0.0,
    0.3, 0.0,    // invisible below 0.3
    0.4, 0.05,   // barely visible
    0.5, 0.12,
    0.6, 0.25,
    0.8, 0.42,
    1.0, 0.58,
  ];
}
