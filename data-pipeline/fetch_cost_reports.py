"""
Fetch hospital payer mix data from CMS.
Uses Medicare Inpatient Hospitals by Provider as the primary source (simpler than cost reports).
Falls back to a beds-based estimate if unavailable.
Output: output/hospital_payer_mix.csv
"""
import os
import requests
import pandas as pd
from tqdm import tqdm

OUTPUT_DIR = 'output'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'hospital_payer_mix.csv')
CACHE_FILE = os.path.join(OUTPUT_DIR, 'cms_medicare_utilization.json')

# CMS Medicare Inpatient Hospitals by Provider
# This gives Medicare discharges, charges, and payments per hospital
MEDICARE_UTIL_URL = 'https://data.cms.gov/provider-data/api/1/datastore/query/4pq5-n9py'

# Alternative: Medicare Inpatient Hospitals by Provider and Service
MEDICARE_ALT_URL = 'https://data.cms.gov/provider-summary-by-type-of-service/medicare-inpatient-hospitals/medicare-inpatient-hospitals-by-provider-and-service'


def fetch_medicare_utilization():
    """Fetch Medicare utilization per hospital."""
    if os.path.exists(CACHE_FILE):
        print(f'Using cached Medicare utilization: {CACHE_FILE}')
        import json
        with open(CACHE_FILE) as f:
            return json.load(f)

    print('Fetching Medicare utilization from CMS...')
    all_records = []
    offset = 0
    limit = 500

    # Try the primary endpoint
    url = MEDICARE_UTIL_URL
    while True:
        try:
            resp = requests.get(url, params={'offset': offset, 'limit': limit}, timeout=60)
            if resp.status_code != 200:
                print(f'API returned {resp.status_code}, trying alternative...')
                break
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
        except Exception as e:
            print(f'Error fetching: {e}')
            break

    if not all_records:
        print('Primary endpoint failed. Trying Medicare Inpatient by Provider & Service...')
        all_records = _try_alternative_endpoint()

    if all_records:
        import json
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(all_records, f)
        print(f'Cached {len(all_records)} records')

    return all_records


def _try_alternative_endpoint():
    """Try fetching from CMS provider summary datasets."""
    # Try several known CMS dataset IDs for Medicare utilization
    dataset_ids = ['4pq5-n9py', 'tcsp-6e99', 'drm2-bg2o']
    for dsid in dataset_ids:
        url = f'https://data.cms.gov/provider-data/api/1/datastore/query/{dsid}'
        try:
            resp = requests.get(url, params={'limit': 10}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('results'):
                    print(f'Found working dataset: {dsid}')
                    # Fetch all
                    all_records = []
                    offset = 0
                    while True:
                        resp = requests.get(url, params={'offset': offset, 'limit': 500}, timeout=60)
                        results = resp.json().get('results', [])
                        if not results:
                            break
                        all_records.extend(results)
                        total = resp.json().get('count', 0)
                        if len(all_records) >= total:
                            break
                        offset += 500
                    return all_records
        except Exception:
            continue
    return []


def parse_utilization(records):
    """Parse Medicare utilization records into per-hospital payer data."""
    if not records:
        print('No Medicare utilization data available. Will use hospital-level estimates.')
        return pd.DataFrame()

    # Examine field names from first record
    sample = records[0]
    print(f'Available fields: {list(sample.keys())[:20]}')

    rows = []
    for r in records:
        row = {
            'facility_id': (
                r.get('facility_id', '') or
                r.get('provider_id', '') or
                r.get('provider_ccn', '') or
                r.get('ccn', '')
            ),
            'medicare_discharges': _to_num(
                r.get('total_discharges', r.get('medicare_discharges', r.get('tot_dschrgs', 0)))
            ),
            'total_charges_medicare': _to_num(
                r.get('average_covered_charges', r.get('covered_charges', r.get('avg_submtd_cvrd_chrg', 0)))
            ),
            'total_payments_medicare': _to_num(
                r.get('average_total_payments', r.get('total_payments', r.get('avg_tot_pymt_amt', 0)))
            ),
            'medicare_payment_per_discharge': _to_num(
                r.get('average_medicare_payments', r.get('avg_mdcr_pymt_amt', 0))
            ),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    df['facility_id'] = df['facility_id'].astype(str).str.strip()

    # If there are multiple rows per facility (by DRG), aggregate
    if df['facility_id'].duplicated().any():
        print(f'Aggregating {len(df)} rows by facility...')
        agg = df.groupby('facility_id').agg({
            'medicare_discharges': 'sum',
            'total_charges_medicare': 'sum',
            'total_payments_medicare': 'sum',
            'medicare_payment_per_discharge': 'mean',
        }).reset_index()
        df = agg

    print(f'Parsed Medicare utilization for {len(df)} facilities')
    return df


def _to_num(v):
    try:
        return float(str(v).replace(',', '').replace('$', ''))
    except (ValueError, TypeError):
        return 0


def compute_payer_estimates(hospitals_df, utilization_df):
    """
    Compute payer mix estimates. Join utilization to hospital inventory
    and estimate government payer share.
    """
    if utilization_df.empty:
        # Fallback: estimate from hospital type
        print('Using type-based payer mix estimates (no CMS utilization data)')
        hospitals_df['medicare_days_share'] = 0.45  # national average
        hospitals_df['medicaid_days_share'] = 0.20
        hospitals_df['govt_days_share'] = 0.65
        # Critical Access Hospitals have higher government share
        cah_mask = hospitals_df['hospital_type'].str.contains('Critical', case=False, na=False)
        hospitals_df.loc[cah_mask, 'govt_days_share'] = 0.75
        hospitals_df.loc[cah_mask, 'medicare_days_share'] = 0.55
        return hospitals_df[['facility_id', 'medicare_days_share', 'medicaid_days_share',
                             'govt_days_share', 'medicare_discharges']].copy() if 'medicare_discharges' in hospitals_df.columns else hospitals_df

    # Join
    merged = hospitals_df[['facility_id', 'beds', 'hospital_type']].merge(
        utilization_df, on='facility_id', how='left'
    )

    # Compute Medicare intensity: discharges per bed (annual)
    merged['medicare_intensity'] = merged['medicare_discharges'] / merged['beds'].clip(lower=1)

    # Estimate government payer share from Medicare intensity
    # National average: ~130 Medicare discharges per bed per year
    # For a hospital with intensity > 130, Medicare share is higher than average
    # Approximate: medicare_days_share ≈ medicare_intensity / 250 (typical total discharges/bed)
    merged['medicare_days_share'] = (merged['medicare_intensity'] / 250).clip(upper=0.85)

    # Medicaid estimate: ~20% for acute care, higher for children's hospitals
    merged['medicaid_days_share'] = 0.20
    children_mask = merged['hospital_type'].str.contains('Children', case=False, na=False)
    merged.loc[children_mask, 'medicaid_days_share'] = 0.40

    # Fallback for hospitals without utilization data
    no_data = merged['medicare_discharges'].isna() | (merged['medicare_discharges'] == 0)
    merged.loc[no_data, 'medicare_days_share'] = 0.45
    cah_mask = merged['hospital_type'].str.contains('Critical', case=False, na=False)
    merged.loc[no_data & cah_mask, 'medicare_days_share'] = 0.55

    merged['govt_days_share'] = (merged['medicare_days_share'] + merged['medicaid_days_share']).clip(upper=0.95)

    result = merged[['facility_id', 'medicare_days_share', 'medicaid_days_share',
                      'govt_days_share', 'medicare_discharges', 'total_charges_medicare',
                      'total_payments_medicare']].copy()

    return result


def fetch_and_process(hospitals_df=None):
    """Main pipeline entry point."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    records = fetch_medicare_utilization()
    utilization_df = parse_utilization(records)

    if hospitals_df is None:
        hosp_file = os.path.join(OUTPUT_DIR, 'hospitals_raw.csv')
        if os.path.exists(hosp_file):
            hospitals_df = pd.read_csv(hosp_file, dtype={'facility_id': str, 'county_fips': str})
        else:
            print('ERROR: Run fetch_hospitals.py first')
            return pd.DataFrame()

    result = compute_payer_estimates(hospitals_df, utilization_df)
    result.to_csv(OUTPUT_FILE, index=False)
    print(f'\nSaved payer mix for {len(result)} hospitals to {OUTPUT_FILE}')

    # Validation
    print(f'\n=== Validation ===')
    print(f'Hospitals with Medicare data: {(result["medicare_discharges"] > 0).sum() if "medicare_discharges" in result.columns else "N/A"}')
    if 'govt_days_share' in result.columns:
        print(f'Govt payer share — mean: {result["govt_days_share"].mean():.3f}')
        print(f'Govt payer share — median: {result["govt_days_share"].median():.3f}')

    return result


if __name__ == '__main__':
    fetch_and_process()
