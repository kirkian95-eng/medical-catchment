"""
Fetch hospital payer mix from CMS Medicare Inpatient Hospitals - by Provider.
Computes medicare_intensity (discharges/beds) and estimates government payer share.
Output: output/hospital_payer_mix.csv
"""
import os
import io
import requests
import pandas as pd

OUTPUT_DIR = 'output'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'hospital_payer_mix.csv')
CACHE_FILE = os.path.join(OUTPUT_DIR, 'cms_medicare_inpatient_provider.csv')

# Medicare Inpatient Hospitals - by Provider, Data Year 2023
MEDICARE_CSV_URL = 'https://data.cms.gov/sites/default/files/2025-05/10e4b7e9-40c5-437b-b4d6-61801b6681f2/MUP_INP_RY25_P04_V10_DY23_Prv.CSV'


def fetch_medicare_data():
    """Download Medicare Inpatient by Provider CSV."""
    if os.path.exists(CACHE_FILE):
        print(f'Using cached Medicare data: {CACHE_FILE}')
        return pd.read_csv(CACHE_FILE, dtype={'Rndrng_Prvdr_CCN': str})

    print('Downloading Medicare Inpatient by Provider (DY2023)...')
    resp = requests.get(MEDICARE_CSV_URL, timeout=120)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text), dtype={'Rndrng_Prvdr_CCN': str})
    df.to_csv(CACHE_FILE, index=False)
    print(f'Downloaded {len(df)} provider records')
    return df


def compute_payer_mix(medicare_df, hospitals_df):
    """
    Compute government payer share per hospital using Medicare utilization data.

    Key insight from the spec: medicare_intensity = medicare_discharges / beds
    National avg is ~130 discharges/bed/year. Total discharges/bed ~250/year.
    So medicare_days_share ≈ medicare_discharges / (beds * 250).

    Also use dual-eligible count to estimate Medicaid overlap.
    """
    # Standardize CCN to 6 chars
    medicare_df['facility_id'] = medicare_df['Rndrng_Prvdr_CCN'].astype(str).str.zfill(6)

    # Aggregate by facility (should already be one row per provider, but be safe)
    med = medicare_df.groupby('facility_id').agg(
        medicare_discharges=('Tot_Dschrgs', 'sum'),
        medicare_covered_days=('Tot_Cvrd_Days', 'sum'),
        medicare_total_days=('Tot_Days', 'sum'),
        medicare_total_charges=('Tot_Submtd_Cvrd_Chrg', 'sum'),
        medicare_total_payments=('Tot_Pymt_Amt', 'sum'),
        medicare_payments=('Tot_Mdcr_Pymt_Amt', 'sum'),
        total_beneficiaries=('Tot_Benes', 'sum'),
        dual_eligible_count=('Bene_Dual_Cnt', 'sum'),
        avg_age=('Bene_Avg_Age', 'mean'),
    ).reset_index()

    # Merge with hospital inventory to get bed counts
    hosp = hospitals_df[['facility_id', 'beds', 'hospital_type']].copy()
    hosp['facility_id'] = hosp['facility_id'].astype(str).str.zfill(6)
    merged = hosp.merge(med, on='facility_id', how='left')

    # Compute Medicare intensity
    merged['beds'] = pd.to_numeric(merged['beds'], errors='coerce').fillna(0)
    merged['medicare_discharges'] = pd.to_numeric(merged['medicare_discharges'], errors='coerce').fillna(0)
    merged['medicare_covered_days'] = pd.to_numeric(merged['medicare_covered_days'], errors='coerce').fillna(0)
    merged['dual_eligible_count'] = pd.to_numeric(merged['dual_eligible_count'], errors='coerce').fillna(0)
    merged['total_beneficiaries'] = pd.to_numeric(merged['total_beneficiaries'], errors='coerce').fillna(0)

    # Medicare days share: medicare covered days / estimated total inpatient days
    # Estimated total inpatient days ≈ beds * 365 * occupancy_rate (~0.65 national avg)
    estimated_total_days = merged['beds'].clip(lower=1) * 365 * 0.65
    merged['medicare_days_share'] = (merged['medicare_covered_days'] / estimated_total_days).clip(0, 0.95)

    # Dual-eligible share among Medicare patients → proxy for Medicaid overlap
    merged['dual_share'] = (
        merged['dual_eligible_count'] / merged['total_beneficiaries'].clip(lower=1)
    ).clip(0, 1)

    # Medicaid estimate: national avg ~20% of inpatient days are Medicaid
    # Adjust by dual share (high dual = high Medicaid overlap)
    # Base Medicaid share + bonus for dual-eligible proportion
    merged['medicaid_days_share'] = (0.12 + merged['dual_share'] * 0.15).clip(0, 0.50)

    # Government share = Medicare + Medicaid (with some overlap via duals)
    merged['govt_days_share'] = (merged['medicare_days_share'] + merged['medicaid_days_share']).clip(0, 0.95)

    # Fallback for hospitals with no Medicare data
    no_data = merged['medicare_discharges'] == 0
    no_data_count = no_data.sum()
    if no_data_count > 0:
        # Estimate from hospital type
        cah_mask = merged['hospital_type'].str.contains('Critical', case=False, na=False)
        merged.loc[no_data & cah_mask, 'medicare_days_share'] = 0.50
        merged.loc[no_data & cah_mask, 'medicaid_days_share'] = 0.18
        merged.loc[no_data & cah_mask, 'govt_days_share'] = 0.68

        merged.loc[no_data & ~cah_mask, 'medicare_days_share'] = 0.38
        merged.loc[no_data & ~cah_mask, 'medicaid_days_share'] = 0.15
        merged.loc[no_data & ~cah_mask, 'govt_days_share'] = 0.53

        print(f'  {no_data_count} hospitals without Medicare data — used type-based estimates')

    result = merged[['facility_id', 'medicare_days_share', 'medicaid_days_share',
                      'govt_days_share', 'medicare_discharges',
                      'medicare_total_charges', 'medicare_payments']].copy()
    result = result.rename(columns={'medicare_total_charges': 'total_charges_medicare',
                                     'medicare_payments': 'total_payments_medicare'})

    return result


def fetch_and_process(hospitals_df=None):
    """Main pipeline entry point."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    medicare_df = fetch_medicare_data()

    if hospitals_df is None:
        hosp_file = os.path.join(OUTPUT_DIR, 'hospitals_raw.csv')
        if os.path.exists(hosp_file):
            hospitals_df = pd.read_csv(hosp_file, dtype={'facility_id': str, 'county_fips': str})
        else:
            print('ERROR: Run fetch_hospitals.py first')
            return pd.DataFrame()

    result = compute_payer_mix(medicare_df, hospitals_df)
    result.to_csv(OUTPUT_FILE, index=False)
    print(f'\nSaved payer mix for {len(result)} hospitals to {OUTPUT_FILE}')

    # Validation
    has_data = result['medicare_discharges'] > 0
    print(f'\n=== Validation ===')
    print(f'Hospitals with real Medicare data: {has_data.sum()}/{len(result)}')
    print(f'Govt payer share — mean:   {result["govt_days_share"].mean():.3f}')
    print(f'Govt payer share — median: {result["govt_days_share"].median():.3f}')
    print(f'Govt payer share — min:    {result["govt_days_share"].min():.3f}')
    print(f'Govt payer share — max:    {result["govt_days_share"].max():.3f}')
    print(f'Unique values: {result["govt_days_share"].nunique()}')
    print(f'\nDistribution:')
    bins = [0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    print(pd.cut(result['govt_days_share'], bins=bins).value_counts().sort_index().to_string())

    return result


if __name__ == '__main__':
    fetch_and_process()
