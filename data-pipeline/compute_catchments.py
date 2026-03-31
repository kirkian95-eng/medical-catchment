"""
Compute catchment areas for medical hubs.
Assigns every county in contiguous US to its nearest hub (weighted by hospital size).
Output: output/national_catchments.json, output/hubs/{cbsa_code}.json
"""
import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
from shapely.ops import unary_union

OUTPUT_DIR = 'output'
HUBS_DIR = os.path.join(OUTPUT_DIR, 'hubs')

# Max catchment distance in miles (beyond this, county is unassigned / goes to nearest anyway)
MAX_CATCHMENT_MILES = 120

# Earth radius in miles for haversine
EARTH_RADIUS_MILES = 3959


def haversine_miles(lat1, lon1, lat2, lon2):
    """Compute haversine distance in miles between two points."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return EARTH_RADIUS_MILES * c


def load_data():
    """Load hub rankings, hospital inventory, county geometries, and population."""
    with open(os.path.join(OUTPUT_DIR, 'hub_rankings.json')) as f:
        rankings = json.load(f)

    hospitals = pd.read_csv(
        os.path.join(OUTPUT_DIR, 'hospitals_raw.csv'),
        dtype={'facility_id': str, 'county_fips': str}
    )

    payer = pd.read_csv(
        os.path.join(OUTPUT_DIR, 'hospital_payer_mix.csv'),
        dtype={'facility_id': str}
    )
    payer_cols = ['facility_id'] + [c for c in payer.columns if c not in hospitals.columns]
    hospitals = hospitals.merge(payer[payer_cols], on='facility_id', how='left')

    counties_gdf = gpd.read_file(os.path.join(OUTPUT_DIR, 'counties.geojson'))

    population = pd.read_csv(
        os.path.join(OUTPUT_DIR, 'county_population.csv'),
        dtype={'county_fips': str, 'state_fips': str, 'cbsa_code': str}
    )

    return rankings, hospitals, counties_gdf, population


def assign_counties_to_hubs(rankings, hospitals, counties_gdf, population):
    """
    Assign each county to the nearest hub using size-weighted distance.
    effective_distance = actual_distance / log2(hub_beds + 1)
    """
    # Build hub list with coordinates and total beds
    hub_cbsas = {r['cbsa_code'] for r in rankings}

    # Map hospitals to CBSAs
    xw_file = os.path.join(OUTPUT_DIR, 'cbsa_crosswalk.csv')
    xw = pd.read_csv(xw_file, dtype=str) if os.path.exists(xw_file) else pd.DataFrame()
    if not xw.empty:
        county_to_cbsa = dict(zip(xw['county_fips'], xw['cbsa_code']))
        hospitals['cbsa_code'] = hospitals['county_fips'].map(county_to_cbsa)

    # Get all qualifying hospitals (beds >= 25 in qualifying CBSAs)
    qual_hospitals = hospitals[
        (hospitals['cbsa_code'].isin(hub_cbsas)) &
        (hospitals['beds'] >= 25)
    ].copy()

    print(f'Qualifying hospitals for catchment: {len(qual_hospitals)}')

    # For each hub, use the largest hospital's position as the hub center
    hub_info = {}
    for r in rankings:
        cbsa = r['cbsa_code']
        hub_hosps = qual_hospitals[qual_hospitals['cbsa_code'] == cbsa]
        if hub_hosps.empty:
            hub_info[cbsa] = {
                'lat': r['hub_lat'], 'lon': r['hub_lon'],
                'total_beds': r['total_beds'], 'cbsa_name': r['cbsa_name']
            }
        else:
            total_beds = hub_hosps['beds'].sum()
            # Bed-weighted centroid
            wlat = (hub_hosps['lat'] * hub_hosps['beds']).sum() / total_beds
            wlon = (hub_hosps['lon'] * hub_hosps['beds']).sum() / total_beds
            hub_info[cbsa] = {
                'lat': wlat, 'lon': wlon,
                'total_beds': total_beds, 'cbsa_name': r['cbsa_name']
            }

    # Build arrays for vectorized distance computation
    hub_codes = list(hub_info.keys())
    hub_lats = np.array([hub_info[c]['lat'] for c in hub_codes])
    hub_lons = np.array([hub_info[c]['lon'] for c in hub_codes])
    hub_beds = np.array([hub_info[c]['total_beds'] for c in hub_codes])
    hub_weight = np.log2(hub_beds + 1)  # Size weight

    # Get county centroids
    pop_map = dict(zip(population['county_fips'], population['pop_total']))
    pop_65_map = dict(zip(population['county_fips'], population['pop_65_plus']))

    county_assignments = []
    for _, county in counties_gdf.iterrows():
        cfips = county['county_fips']
        clat = county['centroid_lat']
        clon = county['centroid_lon']

        # Compute weighted distance to all hubs
        distances = haversine_miles(clat, clon, hub_lats, hub_lons)
        weighted_distances = distances / hub_weight

        best_idx = np.argmin(weighted_distances)
        best_hub = hub_codes[best_idx]
        best_dist = distances[best_idx]

        # Cap at 120 miles — if nearest hub is farther, assign to closest by beds
        if best_dist > MAX_CATCHMENT_MILES:
            within_range = distances <= MAX_CATCHMENT_MILES
            if within_range.any():
                # Among hubs within range, pick the one with most beds
                candidates = np.where(within_range)[0]
                best_idx = candidates[np.argmax(hub_beds[candidates])]
                best_hub = hub_codes[best_idx]
                best_dist = distances[best_idx]
            # else: keep the nearest hub even though it's >120mi (no orphan counties)

        county_assignments.append({
            'county_fips': cfips,
            'assigned_hub': best_hub,
            'distance_to_hub_miles': round(best_dist, 1),
            'pop_total': pop_map.get(cfips, 0),
            'pop_65_plus': pop_65_map.get(cfips, 0),
        })

    assignments_df = pd.DataFrame(county_assignments)
    print(f'Assigned {len(assignments_df)} counties to {assignments_df["assigned_hub"].nunique()} hubs')

    return assignments_df


def build_national_catchments(assignments_df, counties_gdf, rankings):
    """Build national_catchments.json — dissolved county polygons per hub."""
    output_file = os.path.join(OUTPUT_DIR, 'national_catchments.json')

    # Create MDI lookup
    mdi_map = {r['cbsa_code']: r for r in rankings}

    # Merge assignments with county geometries
    merged = counties_gdf.merge(assignments_df[['county_fips', 'assigned_hub']], on='county_fips')

    features = []
    hubs_with_catchments = merged['assigned_hub'].unique()
    print(f'Building catchment polygons for {len(hubs_with_catchments)} hubs...')

    for cbsa_code in hubs_with_catchments:
        hub_counties = merged[merged['assigned_hub'] == cbsa_code]
        dissolved = unary_union(hub_counties.geometry)

        hub_data = mdi_map.get(cbsa_code, {})
        catchment_pop = assignments_df[assignments_df['assigned_hub'] == cbsa_code]['pop_total'].sum()

        feature = {
            'type': 'Feature',
            'properties': {
                'cbsa_code': cbsa_code,
                'cbsa_name': hub_data.get('cbsa_name', ''),
                'mdi': hub_data.get('mdi', 0),
                'pop_catchment': int(catchment_pop),
                'total_beds': hub_data.get('total_beds', 0),
            },
            'geometry': json.loads(gpd.GeoSeries([dissolved]).to_json())['features'][0]['geometry']
        }
        features.append(feature)

    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }

    with open(output_file, 'w') as f:
        json.dump(geojson, f)

    size_mb = os.path.getsize(output_file) / 1024 / 1024
    print(f'Saved national catchments to {output_file} ({size_mb:.1f} MB)')

    return geojson


def build_hub_details(assignments_df, hospitals, rankings, population):
    """Build per-hub detail JSON files."""
    os.makedirs(HUBS_DIR, exist_ok=True)

    xw_path = os.path.join(OUTPUT_DIR, 'cbsa_crosswalk.csv')
    xw = pd.read_csv(xw_path, dtype=str) if os.path.exists(xw_path) else pd.DataFrame()
    county_to_cbsa = dict(zip(xw['county_fips'], xw['cbsa_code'])) if not xw.empty else {}
    hospitals['cbsa_code'] = hospitals['county_fips'].map(county_to_cbsa)

    county_names = {}
    counties_path = os.path.join(OUTPUT_DIR, 'counties.geojson')
    if os.path.exists(counties_path):
        cg = gpd.read_file(counties_path)
        county_names = dict(zip(cg['county_fips'], cg['county_name']))

    state_fips_to_abbr = {
        '01':'AL','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE',
        '11':'DC','12':'FL','13':'GA','16':'ID','17':'IL','18':'IN','19':'IA',
        '20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI',
        '27':'MN','28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH',
        '34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND','39':'OH','40':'OK',
        '41':'OR','42':'PA','44':'RI','45':'SC','46':'SD','47':'TN','48':'TX',
        '49':'UT','50':'VT','51':'VA','53':'WA','54':'WV','55':'WI','56':'WY',
    }

    employment = pd.read_csv(
        os.path.join(OUTPUT_DIR, 'county_employment.csv'),
        dtype={'county_fips': str, 'cbsa_code': str}
    )

    for r in rankings:
        cbsa = r['cbsa_code']
        hub_assignments = assignments_df[assignments_df['assigned_hub'] == cbsa]

        if hub_assignments.empty:
            continue

        # Hospitals in this hub's CBSA
        hub_hosps = hospitals[hospitals['cbsa_code'] == cbsa].copy()
        hospital_list = []
        for _, h in hub_hosps.iterrows():
            hospital_list.append({
                'facility_id': h['facility_id'],
                'name': h['hospital_name'],
                'beds': int(h['beds']),
                'type': h.get('hospital_type', ''),
                'ownership': h.get('ownership', ''),
                'lat': round(h['lat'], 4),
                'lon': round(h['lon'], 4),
                'govt_payer_share': round(h.get('govt_days_share', 0.6), 3),
                'medicare_discharges': int(h.get('medicare_discharges', 0)) if pd.notna(h.get('medicare_discharges')) else None,
            })

        # Catchment counties
        county_list = []
        for _, ca in hub_assignments.iterrows():
            cfips = ca['county_fips']
            state_abbr = state_fips_to_abbr.get(cfips[:2], '')
            county_list.append({
                'county_fips': cfips,
                'county_name': county_names.get(cfips, ''),
                'state': state_abbr,
                'pop_total': int(ca['pop_total']),
                'pop_65_plus': int(ca['pop_65_plus']),
                'distance_to_hub_miles': ca['distance_to_hub_miles'],
            })

        catchment_pop = hub_assignments['pop_total'].sum()
        catchment_65 = hub_assignments['pop_65_plus'].sum()
        max_radius = hub_assignments['distance_to_hub_miles'].max()
        avg_dist = (
            (hub_assignments['pop_total'] * hub_assignments['distance_to_hub_miles']).sum() /
            max(hub_assignments['pop_total'].sum(), 1)
        )

        # Employment from MSA counties
        msa_counties = hub_hosps['county_fips'].dropna().unique()
        msa_emp = employment[employment['county_fips'].isin(msa_counties)]
        hosp_emp = msa_emp['hospital_employment'].sum() if not msa_emp.empty else r.get('hospital_employment', 0)
        total_emp = msa_emp['total_employment'].sum() if not msa_emp.empty else r.get('total_employment', 0)

        # Bounding box
        lats = [c['lat'] for c in (hospital_list or [{'lat': r['hub_lat'], 'lon': r['hub_lon']}])]
        lons = [c['lon'] for c in (hospital_list or [{'lat': r['hub_lat'], 'lon': r['hub_lon']}])]
        # Expand bbox to include catchment counties
        for c in county_list:
            # Use county centroid from population data
            pass
        # Simple bbox from hospitals + some padding
        lat_pad = max(1.0, max_radius / 69.0)  # ~69 miles per degree
        lon_pad = max(1.5, max_radius / 55.0)
        bbox = [
            round(min(lons) - lon_pad, 2),
            round(min(lats) - lat_pad, 2),
            round(max(lons) + lon_pad, 2),
            round(max(lats) + lat_pad, 2),
        ]

        hub_detail = {
            'cbsa_code': cbsa,
            'cbsa_name': r['cbsa_name'],
            'mdi': r['mdi'],
            'bbox': bbox,
            'hospitals': sorted(hospital_list, key=lambda x: -x['beds']),
            'catchment_counties': sorted(county_list, key=lambda x: -x['pop_total']),
            'summary': {
                'total_beds': int(sum(h['beds'] for h in hospital_list)),
                'catchment_pop': int(catchment_pop),
                'catchment_pop_65_plus': int(catchment_65),
                'catchment_pct_65_plus': round(catchment_65 / max(catchment_pop, 1), 4),
                'max_catchment_radius_miles': round(max_radius, 1),
                'avg_catchment_distance_miles': round(avg_dist, 1),
                'num_counties': len(county_list),
                'hospital_employment': int(hosp_emp) if pd.notna(hosp_emp) else None,
                'msa_total_employment': int(total_emp) if pd.notna(total_emp) else None,
                'hospital_emp_share': round(r.get('component_a_hospital_emp_share', 0), 4),
                'avg_govt_payer_share': round(r.get('component_b_govt_payer_share', 0), 4),
            }
        }

        hub_file = os.path.join(HUBS_DIR, f'{cbsa}.json')
        with open(hub_file, 'w') as f:
            json.dump(hub_detail, f, indent=2)

    print(f'Saved {len(rankings)} hub detail files to {HUBS_DIR}/')


def update_rankings_with_catchments(rankings, assignments_df):
    """Update hub_rankings.json with catchment population data."""
    for r in rankings:
        cbsa = r['cbsa_code']
        hub_assignments = assignments_df[assignments_df['assigned_hub'] == cbsa]
        if not hub_assignments.empty:
            catchment_pop = int(hub_assignments['pop_total'].sum())
            catchment_65 = int(hub_assignments['pop_65_plus'].sum())
            r['pop_catchment'] = catchment_pop
            r['pct_65_plus_catchment'] = round(catchment_65 / max(catchment_pop, 1), 4)
            r['catchment_radius_miles'] = round(hub_assignments['distance_to_hub_miles'].max(), 1)

    output_file = os.path.join(OUTPUT_DIR, 'hub_rankings.json')
    with open(output_file, 'w') as f:
        json.dump(rankings, f, indent=2)
    print(f'Updated hub_rankings.json with catchment data')


def compute_catchments():
    """Main entry point."""
    rankings, hospitals, counties_gdf, population = load_data()

    assignments_df = assign_counties_to_hubs(rankings, hospitals, counties_gdf, population)

    # Validation: every county assigned exactly once
    assert assignments_df['county_fips'].is_unique, 'Duplicate county assignments!'
    total_catchment_pop = assignments_df['pop_total'].sum()
    print(f'Total catchment population: {total_catchment_pop:,}')

    build_national_catchments(assignments_df, counties_gdf, rankings)
    build_hub_details(assignments_df, hospitals, rankings, population)
    update_rankings_with_catchments(rankings, assignments_df)

    # Validation
    print(f'\n=== Validation ===')
    print(f'Counties assigned: {len(assignments_df)}')
    print(f'Hubs with catchments: {assignments_df["assigned_hub"].nunique()}')
    print(f'Total catchment population: {total_catchment_pop:,}')

    # Largest catchments by population
    catchment_pops = assignments_df.groupby('assigned_hub')['pop_total'].sum().sort_values(ascending=False)
    hub_names = {r['cbsa_code']: r['cbsa_name'] for r in rankings}
    print(f'\nTop 10 catchments by population:')
    for cbsa, pop in catchment_pops.head(10).items():
        print(f'  {hub_names.get(cbsa, cbsa)}: {int(pop):,}')


if __name__ == '__main__':
    compute_catchments()
