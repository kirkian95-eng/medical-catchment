"""
Fetch hospital inventory from CMS Hospital General Information + POS for beds.
Geocode via Census ZIP gazetteer.
Output: output/hospitals_raw.csv
"""
import os
import io
import json
import requests
import pandas as pd
from tqdm import tqdm

OUTPUT_DIR = 'output'
CACHE_FILE = os.path.join(OUTPUT_DIR, 'cms_hospitals_raw.csv')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'hospitals_raw.csv')

# CMS Hospital General Information — use metastore to discover CSV URL
CMS_METASTORE_URL = 'https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/xubh-q36u'
CMS_API_URL = 'https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0'

# CMS Provider of Services (POS) — for bed counts
# We'll try multiple approaches for beds
POS_API_URL = 'https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/provider-of-services-file-hospital-other/api'

# Contiguous US + DC
VALID_STATES = {
    'AL','AR','AZ','CA','CO','CT','DC','DE','FL','GA','IA','ID','IL','IN',
    'KS','KY','LA','MA','MD','ME','MI','MN','MO','MS','MT','NC','ND','NE',
    'NH','NJ','NM','NV','NY','OH','OK','OR','PA','RI','SC','SD','TN','TX',
    'UT','VA','VT','WA','WI','WV','WY'
}

VALID_TYPES = {
    'Acute Care Hospitals',
    'Critical Access Hospitals',
    "Children's Hospitals",
}

DROP_KEYWORDS = ['psychiatric', 'rehabilitation', 'long term', 'long-term']
DROP_TYPES_PARTIAL = ['veterans administration', 'department of defense']


def fetch_cms_csv():
    """Fetch hospital data via the CSV download (most reliable)."""
    if os.path.exists(CACHE_FILE):
        print(f'Using cached CMS CSV: {CACHE_FILE}')
        return pd.read_csv(CACHE_FILE, dtype=str)

    # Step 1: get current CSV URL from metastore
    print('Discovering current CMS CSV URL...')
    resp = requests.get(CMS_METASTORE_URL, timeout=30)
    resp.raise_for_status()
    meta = resp.json()

    csv_url = None
    distributions = meta.get('distribution', [])
    for d in distributions:
        dl_url = d.get('downloadURL', '')
        if dl_url.endswith('.csv'):
            csv_url = dl_url
            break

    if not csv_url:
        # Fallback: try API
        print('No CSV URL found in metastore, falling back to API...')
        return fetch_cms_api()

    print(f'Downloading: {csv_url}')
    resp = requests.get(csv_url, timeout=120)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text), dtype=str)
    df.to_csv(CACHE_FILE, index=False)
    print(f'Downloaded {len(df)} records, cached to {CACHE_FILE}')
    return df


def fetch_cms_api():
    """Fallback: fetch via JSON API."""
    cache_json = os.path.join(OUTPUT_DIR, 'cms_hospitals_raw.json')
    if os.path.exists(cache_json):
        with open(cache_json) as f:
            records = json.load(f)
        return pd.DataFrame(records)

    print('Fetching hospitals from CMS API...')
    all_records = []
    offset = 0
    limit = 500

    while True:
        params = {'offset': offset, 'count': 'true', 'limit': limit}
        resp = requests.get(CMS_API_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        results = data.get('results', [])
        if not results:
            break

        all_records.extend(results)
        total = data.get('count', len(all_records))
        print(f'  Fetched {len(all_records)} / {total}')

        if len(all_records) >= total:
            break
        offset += limit

    with open(cache_json, 'w') as f:
        json.dump(all_records, f)
    return pd.DataFrame(all_records)


def normalize_columns(df):
    """Normalize column names from CMS CSV which vary between releases."""
    # First: lowercase and strip all columns
    df.columns = [c.lower().strip() for c in df.columns]

    # Direct mapping from known CMS CSV column names to our standard names
    rename = {
        'facility id': 'facility_id',
        'facility_id': 'facility_id',
        'provider_id': 'facility_id',
        'facility name': 'hospital_name',
        'facility_name': 'hospital_name',
        'hospital_name': 'hospital_name',
        'address': 'address',
        'street_addr': 'address',
        'city/town': 'city',
        'citytown': 'city',
        'city': 'city',
        'state': 'state',
        'state_cd': 'state',
        'zip code': 'zip',
        'zip_code': 'zip',
        'zip_cd': 'zip',
        'county/parish': 'county_name',
        'countyparish': 'county_name',
        'county_name': 'county_name',
        'hospital type': 'hospital_type',
        'hospital_type': 'hospital_type',
        'hospital ownership': 'ownership',
        'hospital_ownership': 'ownership',
    }

    # Only rename columns that exist
    actual_rename = {c: rename[c] for c in df.columns if c in rename}
    df = df.rename(columns=actual_rename)

    print(f'Columns after normalization: {[c for c in df.columns if c in ["facility_id","hospital_name","city","state","zip","county_name","hospital_type","ownership","beds"]]}')
    return df


def filter_hospitals(df):
    """Filter to qualifying hospital types in contiguous US."""
    print(f'Total records from CMS: {len(df)}')

    # Filter states
    if 'state' in df.columns:
        df = df[df['state'].isin(VALID_STATES)].copy()
        print(f'After state filter: {len(df)}')

    # Filter by type
    if 'hospital_type' in df.columns:
        type_mask = df['hospital_type'].isin(VALID_TYPES)
        # Also partial match
        for vt in VALID_TYPES:
            type_mask |= df['hospital_type'].str.contains(vt.split()[0], case=False, na=False)
        df = df[type_mask].copy()
        print(f'After type filter: {len(df)}')

    # Drop VA/DoD by type
    if 'hospital_type' in df.columns:
        type_lower = df['hospital_type'].str.lower()
        for dp in DROP_TYPES_PARTIAL:
            df = df[~type_lower.str.contains(dp, na=False)]
            type_lower = df['hospital_type'].str.lower()
        print(f'After VA/DoD exclusion: {len(df)}')

    # Drop by name keywords
    if 'hospital_name' in df.columns:
        name_lower = df['hospital_name'].str.lower()
        for kw in DROP_KEYWORDS:
            df = df[~name_lower.str.contains(kw, na=False)]
            name_lower = df['hospital_name'].str.lower()
        print(f'After keyword exclusion: {len(df)}')

    # Dedup
    if 'facility_id' in df.columns:
        df = df.drop_duplicates(subset='facility_id', keep='first')
        print(f'After dedup: {len(df)}')

    return df


def add_bed_counts(df):
    """Fetch bed counts from CMS Provider of Services (POS) file."""
    beds_cache = os.path.join(OUTPUT_DIR, 'pos_beds.json')

    if os.path.exists(beds_cache):
        print('Using cached bed counts...')
        with open(beds_cache) as f:
            bed_map = json.load(f)
    else:
        bed_map = {}
        print('Fetching bed counts from CMS Provider of Services...')

        # POS JSON API — paginate through all records, only pull ID + bed fields
        pos_api = 'https://data.cms.gov/data-api/v1/dataset/0769ae17-aee8-4a3d-975e-094c3c26785f/data'
        offset = 0
        page_size = 500

        while True:
            try:
                resp = requests.get(pos_api, params={'size': page_size, 'offset': offset}, timeout=60)
                if resp.status_code != 200:
                    print(f'  POS API returned {resp.status_code} at offset {offset}')
                    break
                records = resp.json()
                if not records:
                    break
                for r in records:
                    ccn = str(r.get('PRVDR_NUM', '')).strip()
                    beds = r.get('BED_CNT') or r.get('CRTFD_BED_CNT') or '0'
                    try:
                        beds_int = int(float(str(beds)))
                    except (ValueError, TypeError):
                        beds_int = 0
                    if ccn and beds_int > 0:
                        bed_map[ccn] = beds_int
                if len(records) < page_size:
                    break
                offset += page_size
                if offset % 5000 == 0:
                    print(f'  POS: fetched {offset} records, {len(bed_map)} with beds...')
            except Exception as e:
                print(f'  POS API error at offset {offset}: {e}')
                break

        print(f'POS bed data: {len(bed_map)} facilities with bed counts')

        with open(beds_cache, 'w') as f:
            json.dump(bed_map, f)

    # Apply bed counts
    if 'beds' not in df.columns:
        df['beds'] = 0

    matched = 0
    for idx in df.index:
        fid = str(df.at[idx, 'facility_id']).strip()
        if fid in bed_map:
            df.at[idx, 'beds'] = bed_map[fid]
            matched += 1

    df['beds'] = pd.to_numeric(df['beds'], errors='coerce').fillna(0).astype(int)
    print(f'Bed counts matched: {matched}/{len(df)}')

    # For hospitals with 0 beds, estimate from type
    zero_bed_mask = df['beds'] == 0
    if zero_bed_mask.any() and 'hospital_type' in df.columns:
        print(f'Estimating beds for {zero_bed_mask.sum()} remaining hospitals without bed data...')
        type_estimates = {
            'Acute Care Hospitals': 150,
            'Critical Access Hospitals': 25,
            "Children's Hospitals": 100,
        }
        for htype, est in type_estimates.items():
            mask = zero_bed_mask & (df['hospital_type'] == htype)
            df.loc[mask, 'beds'] = est

    return df


def geocode_from_cms_birthing(df):
    """First-pass geocoding: CMS Birthing Friendly dataset has lat/lon for ~2,265 hospitals."""
    cache = os.path.join(OUTPUT_DIR, 'cms_birthing_geocodes.json')

    if os.path.exists(cache):
        with open(cache) as f:
            coords_map = json.load(f)
    else:
        print('Fetching geocoded coords from CMS Birthing Friendly dataset...')
        coords_map = {}
        # Use the CMS API
        url = 'https://data.cms.gov/provider-data/api/1/datastore/query/hbf-map/0'
        offset = 0
        while True:
            resp = requests.get(url, params={'limit': 500, 'offset': offset}, timeout=30)
            if resp.status_code != 200:
                break
            data = resp.json()
            results = data.get('results', [])
            if not results:
                break
            for r in results:
                # Match by name+city+state since this dataset lacks facility_id
                key = (r.get('name', '').upper().strip(),
                       r.get('city', '').upper().strip(),
                       r.get('state', '').upper().strip())
                lat = r.get('lat')
                lon = r.get('lon')
                if lat and lon:
                    try:
                        coords_map[f'{key[0]}|{key[1]}|{key[2]}'] = [float(lat), float(lon)]
                    except (ValueError, TypeError):
                        pass
            if len(results) < 500:
                break
            offset += 500

        with open(cache, 'w') as f:
            json.dump(coords_map, f)
        print(f'  Cached {len(coords_map)} geocoded hospitals')

    if 'lat' not in df.columns:
        df['lat'] = None
    if 'lon' not in df.columns:
        df['lon'] = None

    filled = 0
    for idx in df.index:
        if pd.notna(df.at[idx, 'lat']) and pd.notna(df.at[idx, 'lon']):
            continue
        key = f'{str(df.at[idx, "hospital_name"]).upper().strip()}|{str(df.at[idx, "city"]).upper().strip()}|{str(df.at[idx, "state"]).upper().strip()}'
        if key in coords_map:
            df.at[idx, 'lat'], df.at[idx, 'lon'] = coords_map[key]
            filled += 1

    print(f'CMS Birthing geocoding: filled {filled}/{len(df)}')
    return df


def geocode_from_zip(df):
    """Fallback geocoding: ZIP code centroids from Census gazetteer."""
    if 'lat' in df.columns and df['lat'].notna().sum() > len(df) * 0.9:
        print(f'Already have {df["lat"].notna().sum()}/{len(df)} coordinates, skipping ZIP geocoding')
        return df

    gaz_file = os.path.join(OUTPUT_DIR, 'zip_gazetteer.txt')
    if not os.path.exists(gaz_file):
        print('Downloading ZIP code gazetteer...')
        import zipfile as zf_mod
        url = 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip'
        zip_path = os.path.join(OUTPUT_DIR, 'gaz_zcta.zip')
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with open(zip_path, 'wb') as f:
            f.write(resp.content)
        with zf_mod.ZipFile(zip_path) as zf:
            txt_name = [n for n in zf.namelist() if n.endswith('.txt')][0]
            with zf.open(txt_name) as src, open(gaz_file, 'wb') as dst:
                dst.write(src.read())

    gaz = pd.read_csv(gaz_file, sep='\t', dtype={'GEOID': str})
    gaz.columns = [c.strip() for c in gaz.columns]
    zip_to_coords = dict(zip(gaz['GEOID'], zip(gaz['INTPTLAT'], gaz['INTPTLONG'])))

    df['lat'] = pd.to_numeric(df.get('lat'), errors='coerce')
    df['lon'] = pd.to_numeric(df.get('lon'), errors='coerce')

    filled = 0
    for idx in df.index:
        if pd.notna(df.at[idx, 'lat']) and pd.notna(df.at[idx, 'lon']):
            continue
        z = str(df.at[idx, 'zip']).split('.')[0].split('-')[0].zfill(5)
        if z in zip_to_coords:
            df.at[idx, 'lat'], df.at[idx, 'lon'] = zip_to_coords[z]
            filled += 1

    still_missing = (df['lat'].isna() | df['lon'].isna()).sum()
    print(f'ZIP geocoding: filled {filled}, still missing {still_missing}')

    df = df.dropna(subset=['lat', 'lon'])
    return df


def add_county_fips(df):
    """Add county FIPS from Census county name lookup."""
    fips_file = os.path.join(OUTPUT_DIR, 'county_fips_lookup.csv')
    if not os.path.exists(fips_file):
        print('Downloading county FIPS lookup...')
        url = 'https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt'
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(fips_file, 'w') as f:
            f.write(resp.text)

    fips_df = pd.read_csv(fips_file, sep='|', dtype=str)
    fips_df.columns = [c.strip() for c in fips_df.columns]

    fips_lookup = {}
    for _, row in fips_df.iterrows():
        state = str(row.get('STUSAB', '') or row.get('STATE', '')).strip()
        county = str(row.get('COUNTYNAME', '') or row.get('COUNTY_NAME', '')).strip()
        sfips = str(row.get('STATEFP', '') or row.get('STATE_FIPS', '')).strip()
        cfips = str(row.get('COUNTYFP', '') or row.get('COUNTY_FIPS', '')).strip()
        if state and county and sfips and cfips:
            full_fips = sfips.zfill(2) + cfips.zfill(3)
            county_norm = county.lower().replace(' county', '').replace(' parish', '').replace(' borough', '').replace(' census area', '').replace(' municipality', '').strip()
            fips_lookup[(state, county_norm)] = full_fips

    df['county_fips'] = None
    matched = 0
    for idx in df.index:
        state = df.at[idx, 'state']
        county = str(df.at[idx, 'county_name']).lower().replace(' county', '').replace(' parish', '').replace(' borough', '').replace(' census area', '').replace(' municipality', '').strip()
        key = (state, county)
        if key in fips_lookup:
            df.at[idx, 'county_fips'] = fips_lookup[key]
            matched += 1

    print(f'County FIPS matched: {matched}/{len(df)}')
    return df


def fetch_and_process():
    """Main pipeline entry point."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Fetch hospital data
    df = fetch_cms_csv()
    df = normalize_columns(df)
    df = filter_hospitals(df)
    df = add_bed_counts(df)
    df = geocode_from_cms_birthing(df)
    df = geocode_from_zip(df)
    df = add_county_fips(df)

    # Keep only needed columns
    cols = ['facility_id', 'hospital_name', 'address', 'city', 'state', 'zip',
            'county_fips', 'county_name', 'lat', 'lon', 'beds', 'hospital_type', 'ownership']
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(OUTPUT_FILE, index=False)
    print(f'\nSaved {len(df)} hospitals to {OUTPUT_FILE}')

    # Validation
    print(f'\n=== Validation ===')
    print(f'Total hospitals: {len(df)}')
    print(f'Total beds: {df["beds"].sum():,}')
    print(f'States represented: {df["state"].nunique()}')
    if 'hospital_type' in df.columns:
        print(f'Type distribution:')
        print(df['hospital_type'].value_counts().to_string())
    print(f'\nTop 10 by bed count:')
    print(df.nlargest(10, 'beds')[['hospital_name', 'city', 'state', 'beds']].to_string())

    return df


if __name__ == '__main__':
    fetch_and_process()
