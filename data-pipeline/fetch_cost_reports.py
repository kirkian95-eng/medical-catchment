"""
Fetch hospital payer mix AND FTE employment from CMS Hospital Provider Cost Report.
Also supplements with Medicare Inpatient by Provider for discharge-level detail.
Output: output/hospital_payer_mix.csv (includes FTE column for employment bypass)
"""
import os
import io
import requests
import pandas as pd

OUTPUT_DIR = 'output'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'hospital_payer_mix.csv')
COST_REPORT_CACHE = os.path.join(OUTPUT_DIR, 'cost_report_2023.csv')
MEDICARE_CACHE = os.path.join(OUTPUT_DIR, 'cms_medicare_inpatient_provider.csv')

# CMS Hospital Provider Cost Report — 2023
COST_REPORT_URL = 'https://data.cms.gov/sites/default/files/2026-01/3c39f483-c7e0-4025-8396-4df76942e10f/CostReport_2023_Final.csv'

# Medicare Inpatient Hospitals - by Provider, Data Year 2023
MEDICARE_CSV_URL = 'https://data.cms.gov/sites/default/files/2025-05/10e4b7e9-40c5-437b-b4d6-61801b6681f2/MUP_INP_RY25_P04_V10_DY23_Prv.CSV'


def fetch_cost_report():
    """Download CMS Hospital Provider Cost Report extract."""
    if os.path.exists(COST_REPORT_CACHE):
        print(f'Using cached cost report: {COST_REPORT_CACHE}')
        return pd.read_csv(COST_REPORT_CACHE, dtype={'Provider CCN': str})

    print('Downloading Hospital Provider Cost Report (2023)...')
    resp = requests.get(COST_REPORT_URL, timeout=120)
    resp.raise_for_status()
    with open(COST_REPORT_CACHE, 'w') as f:
        f.write(resp.text)
    df = pd.read_csv(io.StringIO(resp.text), dtype={'Provider CCN': str})
    print(f'Downloaded {len(df)} cost report records')
    return df


def fetch_medicare_data():
    """Download Medicare Inpatient by Provider for discharge-level detail."""
    if os.path.exists(MEDICARE_CACHE):
        print(f'Using cached Medicare data: {MEDICARE_CACHE}')
        return pd.read_csv(MEDICARE_CACHE, dtype={'Rndrng_Prvdr_CCN': str})

    print('Downloading Medicare Inpatient by Provider (DY2023)...')
    resp = requests.get(MEDICARE_CSV_URL, timeout=120)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), dtype={'Rndrng_Prvdr_CCN': str})
    df.to_csv(MEDICARE_CACHE, index=False)
    print(f'Downloaded {len(df)} Medicare provider records')
    return df


def compute_payer_mix(cost_df, medicare_df, hospitals_df):
    """
    Compute government payer share AND extract FTE from cost reports.

    Cost report fields used:
    - Total Days Title XVIII = Medicare inpatient days
    - Total Days Title XIX = Medicaid inpatient days
    - Total Days (V + XVIII + XIX + Unknown) = Total inpatient days (all payers)
    - FTE - Employees on Payroll = direct employment count
    - Total Salaries From Worksheet A = total payroll
    """
    # Standardize CCN
    cost_df['facility_id'] = cost_df['Provider CCN'].astype(str).str.zfill(6)

    # Some providers have multiple cost reports (amended/restated). Keep latest.
    cost_df['Fiscal Year End Date'] = pd.to_datetime(cost_df['Fiscal Year End Date'], errors='coerce')
    cost_df = cost_df.sort_values('Fiscal Year End Date', ascending=False).drop_duplicates(
        subset='facility_id', keep='first'
    )

    # Extract key fields
    cr = cost_df[[
        'facility_id',
        'FTE - Employees on Payroll',
        'Total Days Title XVIII',
        'Total Days Title XIX',
        'Total Days (V + XVIII + XIX + Unknown)',
        'Total Bed Days Available',
        'Number of Beds',
        'Total Salaries From Worksheet A',
        'Total Discharges Title XVIII',
        'Total Discharges (V + XVIII + XIX + Unknown)',
    ]].copy()

    cr.columns = [
        'facility_id', 'fte_employees', 'medicare_days', 'medicaid_days',
        'total_days', 'bed_days_available', 'beds_cr', 'total_salaries',
        'medicare_discharges_cr', 'total_discharges',
    ]

    # Convert to numeric
    for col in cr.columns[1:]:
        cr[col] = pd.to_numeric(cr[col], errors='coerce')

    # Compute payer shares from ACTUAL inpatient days
    cr['medicare_days_share'] = (cr['medicare_days'] / cr['total_days'].clip(lower=1)).clip(0, 0.95)
    cr['medicaid_days_share'] = (cr['medicaid_days'] / cr['total_days'].clip(lower=1)).clip(0, 0.95)
    cr['govt_days_share'] = (cr['medicare_days_share'] + cr['medicaid_days_share']).clip(0, 0.95)

    # Compute occupancy
    cr['occupancy'] = (cr['total_days'] / cr['bed_days_available'].clip(lower=1)).clip(0, 1)

    # Also get Medicare discharge data for hospitals not in cost reports
    medicare_df['facility_id'] = medicare_df['Rndrng_Prvdr_CCN'].astype(str).str.zfill(6)
    med_agg = medicare_df.groupby('facility_id').agg(
        medicare_discharges_med=('Tot_Dschrgs', 'sum'),
        medicare_payments=('Tot_Mdcr_Pymt_Amt', 'sum'),
        medicare_charges=('Tot_Submtd_Cvrd_Chrg', 'sum'),
        dual_eligible=('Bene_Dual_Cnt', 'sum'),
        total_beneficiaries=('Tot_Benes', 'sum'),
    ).reset_index()

    # Merge cost report + Medicare data onto hospital inventory
    hosp = hospitals_df[['facility_id', 'beds', 'hospital_type']].copy()
    hosp['facility_id'] = hosp['facility_id'].astype(str).str.zfill(6)

    merged = hosp.merge(cr, on='facility_id', how='left')
    merged = merged.merge(med_agg, on='facility_id', how='left')

    # Use cost report payer share where available; fall back to Medicare-only estimate
    has_cr = merged['total_days'].notna() & (merged['total_days'] > 0)
    no_cr = ~has_cr
    has_med = merged['medicare_discharges_med'].notna() & (merged['medicare_discharges_med'] > 0)

    print(f'Hospitals with cost report payer data: {has_cr.sum()}')
    print(f'Hospitals with Medicare-only data: {(no_cr & has_med).sum()}')
    print(f'Hospitals with no utilization data: {(no_cr & ~has_med).sum()}')

    # For hospitals with Medicare data but no cost report:
    # Estimate using Medicare days from the Medicare file + beds-based total estimate
    beds_num = pd.to_numeric(merged['beds'], errors='coerce').fillna(0)
    est_total_days = beds_num.clip(lower=1) * 365 * 0.65
    dual_share = (
        merged['dual_eligible'].fillna(0) / merged['total_beneficiaries'].fillna(1).clip(lower=1)
    ).clip(0, 1)

    # For Medicare-only fallback: use discharge count as proxy
    # National avg ~5.5 days per discharge
    est_medicare_days = merged['medicare_discharges_med'].fillna(0) * 5.5
    merged.loc[no_cr & has_med, 'medicare_days_share'] = (
        est_medicare_days / est_total_days
    ).clip(0, 0.85).loc[no_cr & has_med]
    merged.loc[no_cr & has_med, 'medicaid_days_share'] = (
        0.10 + dual_share * 0.18
    ).clip(0, 0.50).loc[no_cr & has_med]
    merged.loc[no_cr & has_med, 'govt_days_share'] = (
        merged.loc[no_cr & has_med, 'medicare_days_share'] +
        merged.loc[no_cr & has_med, 'medicaid_days_share']
    ).clip(0, 0.95)

    # For hospitals with neither: type-based fallback
    no_data = no_cr & ~has_med
    cah_mask = merged['hospital_type'].str.contains('Critical', case=False, na=False)
    merged.loc[no_data & cah_mask, 'medicare_days_share'] = 0.50
    merged.loc[no_data & cah_mask, 'medicaid_days_share'] = 0.18
    merged.loc[no_data & cah_mask, 'govt_days_share'] = 0.68
    merged.loc[no_data & ~cah_mask, 'medicare_days_share'] = 0.38
    merged.loc[no_data & ~cah_mask, 'medicaid_days_share'] = 0.15
    merged.loc[no_data & ~cah_mask, 'govt_days_share'] = 0.53

    # Use best available Medicare discharge count
    merged['medicare_discharges'] = merged['medicare_discharges_cr'].fillna(merged['medicare_discharges_med']).fillna(0)

    # Build output
    result = merged[[
        'facility_id', 'medicare_days_share', 'medicaid_days_share', 'govt_days_share',
        'medicare_discharges', 'fte_employees', 'total_salaries',
    ]].copy()
    result['medicare_discharges'] = result['medicare_discharges'].fillna(0)
    result['total_charges_medicare'] = merged['medicare_charges'].fillna(0)
    result['total_payments_medicare'] = merged['medicare_payments'].fillna(0)

    return result


def fetch_and_process(hospitals_df=None):
    """Main pipeline entry point."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cost_df = fetch_cost_report()
    medicare_df = fetch_medicare_data()

    if hospitals_df is None:
        hosp_file = os.path.join(OUTPUT_DIR, 'hospitals_raw.csv')
        if os.path.exists(hosp_file):
            hospitals_df = pd.read_csv(hosp_file, dtype={'facility_id': str, 'county_fips': str})
        else:
            print('ERROR: Run fetch_hospitals.py first')
            return pd.DataFrame()

    result = compute_payer_mix(cost_df, medicare_df, hospitals_df)
    result.to_csv(OUTPUT_FILE, index=False)
    print(f'\nSaved payer mix for {len(result)} hospitals to {OUTPUT_FILE}')

    # Validation
    has_real = result['govt_days_share'].notna()
    print(f'\n=== Validation ===')
    print(f'Govt payer share — mean:   {result["govt_days_share"].mean():.3f}')
    print(f'Govt payer share — median: {result["govt_days_share"].median():.3f}')
    print(f'Govt payer share — min:    {result["govt_days_share"].min():.3f}')
    print(f'Govt payer share — max:    {result["govt_days_share"].max():.3f}')
    print(f'Unique values: {result["govt_days_share"].nunique()}')
    print(f'\nFTE data available: {result["fte_employees"].notna().sum()}/{len(result)}')
    print(f'FTE range: {result["fte_employees"].dropna().min():.0f} — {result["fte_employees"].dropna().max():.0f}')

    bins = [0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    print(f'\nGovt share distribution:')
    print(pd.cut(result['govt_days_share'], bins=bins).value_counts().sort_index().to_string())

    return result


if __name__ == '__main__':
    fetch_and_process()
