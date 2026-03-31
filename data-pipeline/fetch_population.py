"""
Fetch county-level population data from Census ACS 5-year estimates.
Output: output/county_population.csv
"""
import os
import time
import requests
import pandas as pd
from tqdm import tqdm

OUTPUT_DIR = 'output'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'county_population.csv')

ACS_BASE_URL = 'https://api.census.gov/data/2022/acs/acs5'

# Contiguous US state FIPS codes + DC
STATE_FIPS = [
    '01','04','05','06','08','09','10','11','12','13','16','17','18',
    '19','20','21','22','23','24','25','26','27','28','29','30','31','32','33',
    '34','35','36','37','38','39','40','41','42','44','45','46','47','48','49',
    '50','51','53','54','55','56'
]

# Variables for total population + 65+ age groups
# B01003_001E = Total population
# B01001_020E-025E = Males 65+
# B01001_044E-049E = Females 65+
POP_VARS = ['B01003_001E']
AGE_65_MALE = [f'B01001_{i:03d}E' for i in range(20, 26)]
AGE_65_FEMALE = [f'B01001_{i:03d}E' for i in range(44, 50)]
ALL_VARS = POP_VARS + AGE_65_MALE + AGE_65_FEMALE

CBSA_CROSSWALK_URL = 'https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx'

SENTINEL_VALUES = {-666666666, '-666666666', None, ''}


def _clean_value(v):
    if v in SENTINEL_VALUES:
        return 0
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def fetch_county_population():
    """Fetch county population from Census API."""
    if os.path.exists(OUTPUT_FILE):
        print(f'Using cached population data: {OUTPUT_FILE}')
        return pd.read_csv(OUTPUT_FILE, dtype={'county_fips': str, 'state_fips': str, 'cbsa_code': str})

    api_key = os.environ.get('CENSUS_API_KEY', '')
    var_string = ','.join(ALL_VARS)
    all_rows = []

    for state_fips in tqdm(STATE_FIPS, desc='Fetching population'):
        params = {
            'get': var_string,
            'for': 'county:*',
            'in': f'state:{state_fips}',
        }
        if api_key:
            params['key'] = api_key

        for attempt in range(3):
            try:
                resp = requests.get(ACS_BASE_URL, params=params, timeout=30)
                if resp.status_code == 429:
                    time.sleep(5)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                if attempt == 2:
                    print(f'Failed for state {state_fips}: {e}')
                    data = []
                time.sleep(2)

        if not data or len(data) < 2:
            continue

        headers = data[0]
        for row in data[1:]:
            record = dict(zip(headers, row))
            state = record.get('state', state_fips)
            county = record.get('county', '')
            fips = state.zfill(2) + county.zfill(3)

            pop_total = _clean_value(record.get('B01003_001E', 0))
            pop_65_male = sum(_clean_value(record.get(v, 0)) for v in AGE_65_MALE)
            pop_65_female = sum(_clean_value(record.get(v, 0)) for v in AGE_65_FEMALE)
            pop_65_plus = pop_65_male + pop_65_female

            all_rows.append({
                'county_fips': fips,
                'state_fips': state.zfill(2),
                'pop_total': pop_total,
                'pop_65_plus': pop_65_plus,
                'pct_65_plus': pop_65_plus / pop_total if pop_total > 0 else 0,
            })

        time.sleep(0.3)  # Rate limiting

    df = pd.DataFrame(all_rows)
    print(f'Fetched population for {len(df)} counties')
    return df


def add_cbsa(df):
    """Add CBSA codes."""
    csv_path = os.path.join(OUTPUT_DIR, 'cbsa_crosswalk.csv')
    if os.path.exists(csv_path):
        xw = pd.read_csv(csv_path, dtype=str)
    else:
        xls_path = os.path.join(OUTPUT_DIR, 'cbsa_crosswalk.xlsx')
        if not os.path.exists(xls_path):
            print('Downloading CBSA crosswalk...')
            resp = requests.get(CBSA_CROSSWALK_URL, timeout=60)
            resp.raise_for_status()
            with open(xls_path, 'wb') as f:
                f.write(resp.content)

        xw = pd.read_excel(xls_path, dtype=str, skiprows=2)
        xw.columns = [c.strip() for c in xw.columns]

        col_map = {}
        for c in xw.columns:
            cl = c.lower()
            if 'cbsa code' in cl:
                col_map[c] = 'cbsa_code'
            elif 'cbsa title' in cl:
                col_map[c] = 'cbsa_name'
            elif 'fips state' in cl:
                col_map[c] = 'state_fips'
            elif 'fips county' in cl:
                col_map[c] = 'county_fips_part'
        xw = xw.rename(columns=col_map)
        if 'state_fips' in xw.columns and 'county_fips_part' in xw.columns:
            xw['county_fips'] = xw['state_fips'].str.zfill(2) + xw['county_fips_part'].str.zfill(3)
        xw.to_csv(csv_path, index=False)

    xw_slim = xw[['county_fips', 'cbsa_code', 'cbsa_name']].drop_duplicates(subset='county_fips')
    df = df.merge(xw_slim, on='county_fips', how='left')
    return df


def fetch_and_process():
    """Main entry point."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = fetch_county_population()
    df = add_cbsa(df)

    df.to_csv(OUTPUT_FILE, index=False)
    print(f'\nSaved {len(df)} counties to {OUTPUT_FILE}')

    # Validation
    print(f'\n=== Validation ===')
    print(f'Total US population (contiguous): {df["pop_total"].sum():,}')
    print(f'Total 65+ population: {df["pop_65_plus"].sum():,}')
    print(f'National 65+ share: {df["pop_65_plus"].sum() / df["pop_total"].sum():.3f}')
    print(f'Counties with CBSA: {df["cbsa_code"].notna().sum()}/{len(df)}')

    return df


if __name__ == '__main__':
    fetch_and_process()
