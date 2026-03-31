"""
Fetch healthcare employment data from BLS QCEW (annual averages).
Output: output/county_employment.csv
"""
import os
import io
import zipfile
import requests
import pandas as pd
from tqdm import tqdm

OUTPUT_DIR = 'output'
CACHE_DIR = os.path.join(OUTPUT_DIR, 'bls_cache')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'county_employment.csv')

# BLS QCEW annual averages — most recent full year
QCEW_YEAR = '2023'
QCEW_BASE_URL = f'https://data.bls.gov/cew/data/files/{QCEW_YEAR}/csv'
QCEW_ANNUAL_URL = f'{QCEW_BASE_URL}/{QCEW_YEAR}_annual_singlefile.zip'

# NAICS codes we need
NAICS_TOTAL = '10'          # Total, all industries
NAICS_HEALTHCARE = '62'     # Health Care and Social Assistance
NAICS_HOSPITALS = '622'     # Hospitals

# CBSA crosswalk
CBSA_CROSSWALK_URL = 'https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx'

# National beds-to-FTE ratio for estimating suppressed data
BEDS_TO_FTE_RATIO = 5.0


def download_qcew():
    """Download and extract QCEW annual averages file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    extracted = os.path.join(CACHE_DIR, f'{QCEW_YEAR}.annual.singlefile.csv')

    if os.path.exists(extracted):
        print(f'Using cached QCEW data: {extracted}')
        return extracted

    zip_path = os.path.join(CACHE_DIR, f'qcew_{QCEW_YEAR}_annual.zip')
    if not os.path.exists(zip_path):
        print(f'Downloading QCEW {QCEW_YEAR} annual data (~400MB)...')
        resp = requests.get(QCEW_ANNUAL_URL, stream=True, timeout=300)
        resp.raise_for_status()
        total = int(resp.headers.get('content-length', 0))
        with open(zip_path, 'wb') as f:
            with tqdm(total=total, unit='B', unit_scale=True) as pbar:
                for chunk in resp.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
                    pbar.update(len(chunk))

    print('Extracting...')
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        csv_name = [n for n in names if n.endswith('.csv')][0]
        zf.extract(csv_name, CACHE_DIR)
        actual_path = os.path.join(CACHE_DIR, csv_name)
        if actual_path != extracted:
            os.rename(actual_path, extracted)

    return extracted


def load_cbsa_crosswalk():
    """Load county → CBSA crosswalk."""
    xls_path = os.path.join(OUTPUT_DIR, 'cbsa_crosswalk.xlsx')
    csv_path = os.path.join(OUTPUT_DIR, 'cbsa_crosswalk.csv')

    if os.path.exists(csv_path):
        return pd.read_csv(csv_path, dtype=str)

    if not os.path.exists(xls_path):
        print('Downloading CBSA crosswalk...')
        resp = requests.get(CBSA_CROSSWALK_URL, timeout=60)
        resp.raise_for_status()
        with open(xls_path, 'wb') as f:
            f.write(resp.content)

    xw = pd.read_excel(xls_path, dtype=str, skiprows=2)
    xw.columns = [c.strip() for c in xw.columns]

    # Standardize column names
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
        elif 'metropolitan' in cl and 'division' not in cl:
            col_map[c] = 'metro_micro'

    xw = xw.rename(columns=col_map)
    if 'state_fips' in xw.columns and 'county_fips_part' in xw.columns:
        xw['county_fips'] = xw['state_fips'].str.zfill(2) + xw['county_fips_part'].str.zfill(3)
    xw = xw.dropna(subset=['cbsa_code', 'county_fips'])
    xw.to_csv(csv_path, index=False)
    return xw


def process_qcew(csv_path):
    """Extract county-level employment for target NAICS codes."""
    print('Reading QCEW data (this takes a moment)...')

    target_naics = {NAICS_TOTAL, NAICS_HEALTHCARE, NAICS_HOSPITALS}
    rows = []

    usecols = ['area_fips', 'own_code', 'industry_code', 'agglvl_code', 'size_code',
               'annual_avg_emplvl', 'annual_avg_wkly_wage', 'total_annual_wages',
               'disclosure_code']

    chunk_iter = pd.read_csv(csv_path, dtype=str, usecols=usecols, chunksize=500_000)

    for chunk in tqdm(chunk_iter, desc='Processing QCEW'):
        # Keep county-level rows (5-digit FIPS) for target industries, all sizes
        # Include all ownership codes — we'll aggregate below
        mask = (
            chunk['industry_code'].isin(target_naics) &
            chunk['size_code'].eq('0') &
            chunk['area_fips'].str.len().eq(5)  # County-level only
        )
        filtered = chunk[mask]
        if len(filtered) > 0:
            rows.append(filtered)

    if not rows:
        print('ERROR: No QCEW rows matched filters')
        return pd.DataFrame()

    df = pd.concat(rows, ignore_index=True)
    print(f'Extracted {len(df)} QCEW records')

    # Convert numeric columns
    df['annual_avg_emplvl'] = pd.to_numeric(df['annual_avg_emplvl'], errors='coerce')
    df['annual_avg_wkly_wage'] = pd.to_numeric(df['annual_avg_wkly_wage'], errors='coerce')
    df['total_annual_wages'] = pd.to_numeric(df['total_annual_wages'], errors='coerce')

    # For each county + industry, prefer own_code=0 (all ownerships).
    # If not available, sum across own_codes 1-5.
    result_rows = []
    counties = df['area_fips'].unique()

    for fips in tqdm(counties, desc='Pivoting by county'):
        county_data = df[df['area_fips'] == fips]
        row = {'county_fips': fips}

        for naics in target_naics:
            ind_data = county_data[county_data['industry_code'] == naics]
            if ind_data.empty:
                continue

            # Try own_code=0 first (all ownerships combined)
            combined = ind_data[ind_data['own_code'] == '0']
            if not combined.empty:
                r = combined.iloc[0]
                emp = r['annual_avg_emplvl']
                wage = r['annual_avg_wkly_wage']
                total_wages = r['total_annual_wages']
                suppressed = pd.isna(emp) or str(r.get('disclosure_code', '')).strip() not in ('', 'nan')
            else:
                # Sum across ownership types (exclude own_code=0 to avoid double counting)
                parts = ind_data[ind_data['own_code'] != '0']
                emp = parts['annual_avg_emplvl'].sum()
                total_wages = parts['total_annual_wages'].sum()
                wage = total_wages / (emp * 52) if emp > 0 else None
                suppressed = emp == 0

            if naics == NAICS_TOTAL:
                row['total_employment'] = emp if not suppressed else None
                row['total_avg_weekly_wage'] = wage if not suppressed else None
            elif naics == NAICS_HOSPITALS:
                row['hospital_employment'] = emp if not suppressed else None
                row['hospital_avg_weekly_wage'] = wage if not suppressed else None
                row['hospital_suppressed'] = suppressed
            elif naics == NAICS_HEALTHCARE:
                row['healthcare_employment'] = emp if not suppressed else None

        result_rows.append(row)

    result = pd.DataFrame(result_rows)
    result['state_fips'] = result['county_fips'].str[:2]

    return result


def compute_shares(df):
    """Compute employment shares."""
    df['hospital_emp_share'] = df['hospital_employment'] / df['total_employment']
    df['healthcare_emp_share'] = df['healthcare_employment'] / df['total_employment']

    # Payroll share: hospital payroll / total payroll
    # Approximate: (hospital_emp * hospital_wage) / (total_emp * total_wage)
    df['hospital_payroll_share'] = (
        (df['hospital_employment'] * df['hospital_avg_weekly_wage']) /
        (df['total_employment'] * df['total_avg_weekly_wage'])
    )

    return df


def add_cbsa(df, crosswalk):
    """Add CBSA codes to county employment data."""
    xw = crosswalk[['county_fips', 'cbsa_code', 'cbsa_name']].drop_duplicates(subset='county_fips')
    df = df.merge(xw, on='county_fips', how='left')
    matched = df['cbsa_code'].notna().sum()
    print(f'Counties with CBSA assignment: {matched}/{len(df)}')
    return df


def fetch_and_process():
    """Main pipeline entry point."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    csv_path = download_qcew()
    crosswalk = load_cbsa_crosswalk()
    df = process_qcew(csv_path)

    if df.empty:
        print('No employment data extracted.')
        return df

    df = compute_shares(df)
    df = add_cbsa(df, crosswalk)

    # Save
    df.to_csv(OUTPUT_FILE, index=False)
    print(f'\nSaved {len(df)} county employment records to {OUTPUT_FILE}')

    # Validation
    print(f'\n=== Validation ===')
    print(f'Counties with hospital employment data: {df["hospital_employment"].notna().sum()}')
    print(f'Counties with suppressed hospital data: {df.get("hospital_suppressed", pd.Series(dtype=bool)).sum()}')
    has_share = df['hospital_emp_share'].notna()
    if has_share.any():
        print(f'Hospital employment share — median: {df.loc[has_share, "hospital_emp_share"].median():.3f}')
        print(f'Hospital employment share — 95th pct: {df.loc[has_share, "hospital_emp_share"].quantile(0.95):.3f}')
        # Check known medical towns
        for name, fips in [('Olmsted County MN (Mayo)', '27109'), ('Montour County PA (Geisinger)', '42093')]:
            row = df[df['county_fips'] == fips]
            if not row.empty:
                share = row.iloc[0].get('hospital_emp_share')
                print(f'  {name}: hospital_emp_share = {share:.3f}' if pd.notna(share) else f'  {name}: SUPPRESSED')

    return df


if __name__ == '__main__':
    fetch_and_process()
