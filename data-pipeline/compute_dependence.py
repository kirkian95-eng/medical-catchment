"""
Compute the Medical Dependence Index (MDI) for qualifying MSAs.
Output: output/hub_rankings.json
"""
import os
import json
import numpy as np
import pandas as pd

OUTPUT_DIR = 'output'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'hub_rankings.json')

# Thresholds
MIN_MSA_POP = 30_000
MAX_MSA_POP = 2_000_000
MIN_BEDS = 25

# MDI weights
WEIGHT_A = 0.40  # Hospital employment intensity
WEIGHT_B = 0.30  # Government payer intensity
WEIGHT_C = 0.30  # Hospital payroll dominance

# National beds-to-FTE ratio for estimating suppressed employment
BEDS_TO_FTE = 5.0


def load_data():
    """Load all pipeline outputs."""
    hospitals = pd.read_csv(
        os.path.join(OUTPUT_DIR, 'hospitals_raw.csv'),
        dtype={'facility_id': str, 'county_fips': str}
    )
    payer = pd.read_csv(
        os.path.join(OUTPUT_DIR, 'hospital_payer_mix.csv'),
        dtype={'facility_id': str}
    )
    employment = pd.read_csv(
        os.path.join(OUTPUT_DIR, 'county_employment.csv'),
        dtype={'county_fips': str, 'cbsa_code': str}
    )
    population = pd.read_csv(
        os.path.join(OUTPUT_DIR, 'county_population.csv'),
        dtype={'county_fips': str, 'state_fips': str, 'cbsa_code': str}
    )

    return hospitals, payer, employment, population


def join_hospitals_to_cbsa(hospitals, payer, employment):
    """Join hospital data with payer mix and employment, mapped to CBSAs."""
    # Merge payer mix onto hospitals (only payer-specific columns)
    payer_cols = ['facility_id'] + [c for c in payer.columns if c not in hospitals.columns]
    hosp = hospitals.merge(payer[payer_cols], on='facility_id', how='left')

    # Fill missing payer data with defaults
    hosp['govt_days_share'] = hosp['govt_days_share'].fillna(0.60)
    hosp['medicare_days_share'] = hosp['medicare_days_share'].fillna(0.42)

    # Map hospitals to CBSAs via county_fips
    # Load crosswalk
    xw_path = os.path.join(OUTPUT_DIR, 'cbsa_crosswalk.csv')
    if os.path.exists(xw_path):
        xw = pd.read_csv(xw_path, dtype=str)
        xw_slim = xw[['county_fips', 'cbsa_code', 'cbsa_name']].drop_duplicates(subset='county_fips')
        hosp = hosp.merge(xw_slim, on='county_fips', how='left')
    elif 'cbsa_code' not in hosp.columns:
        # Try to get CBSA from employment data
        emp_cbsa = employment[['county_fips', 'cbsa_code']].dropna().drop_duplicates(subset='county_fips')
        hosp = hosp.merge(emp_cbsa, on='county_fips', how='left')

    return hosp


def compute_msa_metrics(hosp, employment, population):
    """Aggregate hospital and employment data to MSA level, compute MDI components."""
    # Filter hospitals with CBSA assignment
    hosp_with_cbsa = hosp[hosp['cbsa_code'].notna()].copy()

    # Aggregate hospitals by CBSA
    cbsa_hospitals = hosp_with_cbsa.groupby('cbsa_code').agg(
        total_beds=('beds', 'sum'),
        num_hospitals=('facility_id', 'nunique'),
        largest_hospital_beds=('beds', 'max'),
        # Bed-weighted government payer share
        weighted_govt_share_num=('beds', lambda x: (x * hosp_with_cbsa.loc[x.index, 'govt_days_share']).sum()),
        weighted_govt_share_den=('beds', 'sum'),
    ).reset_index()

    cbsa_hospitals['govt_payer_share'] = (
        cbsa_hospitals['weighted_govt_share_num'] / cbsa_hospitals['weighted_govt_share_den'].clip(lower=1)
    )

    # Get largest hospital name per CBSA
    largest = hosp_with_cbsa.sort_values('beds', ascending=False).drop_duplicates(subset='cbsa_code')
    largest_map = dict(zip(largest['cbsa_code'], largest['hospital_name']))
    largest_lat = dict(zip(largest['cbsa_code'], largest['lat']))
    largest_lon = dict(zip(largest['cbsa_code'], largest['lon']))
    cbsa_hospitals['largest_hospital'] = cbsa_hospitals['cbsa_code'].map(largest_map)
    cbsa_hospitals['hub_lat'] = cbsa_hospitals['cbsa_code'].map(largest_lat)
    cbsa_hospitals['hub_lon'] = cbsa_hospitals['cbsa_code'].map(largest_lon)

    # Aggregate employment by CBSA — use cost report FTEs as PRIMARY source
    # (bypasses BLS suppression entirely), fall back to BLS where cost report is missing
    fte_by_cbsa = hosp_with_cbsa.groupby('cbsa_code').agg(
        fte_from_cost_reports=('fte_employees', 'sum'),
        fte_count=('fte_employees', lambda x: x.notna().sum()),
        hospital_count=('facility_id', 'nunique'),
    ).reset_index()

    # Also get cost-report-based payroll
    salary_by_cbsa = hosp_with_cbsa.groupby('cbsa_code')['total_salaries'].sum().to_dict()

    emp_by_cbsa = employment.groupby('cbsa_code').agg(
        total_employment=('total_employment', 'sum'),
        hospital_employment_bls=('hospital_employment', 'sum'),
        healthcare_employment=('healthcare_employment', 'sum'),
    ).reset_index()

    emp_by_cbsa = emp_by_cbsa.merge(fte_by_cbsa, on='cbsa_code', how='left')
    beds_by_cbsa = hosp_with_cbsa.groupby('cbsa_code')['beds'].sum().to_dict()

    # Choose best hospital employment source per CBSA
    cr_used = 0
    bls_used = 0
    estimated_count = 0
    for idx in emp_by_cbsa.index:
        cbsa = emp_by_cbsa.at[idx, 'cbsa_code']
        fte_cr = emp_by_cbsa.at[idx, 'fte_from_cost_reports']
        fte_count = emp_by_cbsa.at[idx, 'fte_count']
        hosp_count = emp_by_cbsa.at[idx, 'hospital_count']
        bls_emp = emp_by_cbsa.at[idx, 'hospital_employment_bls']
        beds = beds_by_cbsa.get(cbsa, 0)

        # Prefer cost report FTE if we have it for most hospitals in the CBSA
        if pd.notna(fte_cr) and fte_cr > 0 and fte_count >= hosp_count * 0.5:
            emp_by_cbsa.at[idx, 'hospital_employment'] = fte_cr
            cr_used += 1
        elif pd.notna(bls_emp) and bls_emp > beds * 2:
            # BLS data looks reasonable (not suppressed)
            emp_by_cbsa.at[idx, 'hospital_employment'] = bls_emp
            bls_used += 1
        else:
            # Both suppressed/missing — estimate from beds
            emp_by_cbsa.at[idx, 'hospital_employment'] = beds * BEDS_TO_FTE
            estimated_count += 1

    print(f'Hospital employment source: {cr_used} cost report FTE, {bls_used} BLS, {estimated_count} bed-estimated')

    emp_by_cbsa['hospital_emp_share'] = (
        emp_by_cbsa['hospital_employment'] / emp_by_cbsa['total_employment'].clip(lower=1)
    )

    # Compute payroll share at CBSA level
    # Use cost report total_salaries where available; fall back to BLS wage × employment
    emp_with_payroll = employment[['cbsa_code', 'hospital_avg_weekly_wage',
                                   'total_employment', 'total_avg_weekly_wage']].dropna(
        subset=['cbsa_code', 'total_employment']
    )
    payroll_by_cbsa = emp_with_payroll.groupby('cbsa_code').agg(
        avg_hospital_wage=('hospital_avg_weekly_wage', 'mean'),
        avg_total_wage=('total_avg_weekly_wage', 'mean'),
    ).reset_index()

    payroll_by_cbsa = payroll_by_cbsa.merge(
        emp_by_cbsa[['cbsa_code', 'hospital_employment', 'total_employment']],
        on='cbsa_code', how='left'
    )

    nat_hosp_wage = payroll_by_cbsa['avg_hospital_wage'].dropna().median()

    # Hospital payroll: prefer cost report salaries, else employment × wage
    for idx in payroll_by_cbsa.index:
        cbsa = payroll_by_cbsa.at[idx, 'cbsa_code']
        cr_salary = salary_by_cbsa.get(cbsa, 0)
        if pd.notna(cr_salary) and cr_salary > 0:
            payroll_by_cbsa.at[idx, 'hospital_payroll'] = cr_salary
        else:
            emp = payroll_by_cbsa.at[idx, 'hospital_employment'] or 0
            wage = payroll_by_cbsa.at[idx, 'avg_hospital_wage']
            wage = wage if pd.notna(wage) else nat_hosp_wage
            payroll_by_cbsa.at[idx, 'hospital_payroll'] = emp * wage * 52

    total_wage = payroll_by_cbsa['avg_total_wage'].fillna(payroll_by_cbsa['avg_total_wage'].median())
    total_payroll = payroll_by_cbsa['total_employment'].fillna(0) * total_wage * 52
    payroll_by_cbsa['hospital_payroll_share'] = (
        payroll_by_cbsa['hospital_payroll'] / total_payroll.clip(lower=1)
    )

    # Aggregate population by CBSA
    pop_by_cbsa = population.groupby('cbsa_code').agg(
        pop_msa=('pop_total', 'sum'),
        pop_65_plus_msa=('pop_65_plus', 'sum'),
    ).reset_index()
    pop_by_cbsa['pct_65_plus_msa'] = pop_by_cbsa['pop_65_plus_msa'] / pop_by_cbsa['pop_msa'].clip(lower=1)

    # Get CBSA names
    cbsa_names = {}
    xw_path = os.path.join(OUTPUT_DIR, 'cbsa_crosswalk.csv')
    if os.path.exists(xw_path):
        xw = pd.read_csv(xw_path, dtype=str)
        if 'cbsa_name' in xw.columns:
            cbsa_names = dict(zip(xw['cbsa_code'], xw['cbsa_name']))

    # Merge everything
    msa = cbsa_hospitals.merge(emp_by_cbsa, on='cbsa_code', how='left')
    msa = msa.merge(payroll_by_cbsa[['cbsa_code', 'hospital_payroll_share', 'avg_hospital_wage', 'avg_total_wage']],
                     on='cbsa_code', how='left')
    msa = msa.merge(pop_by_cbsa, on='cbsa_code', how='left')

    # Add CBSA name
    msa['cbsa_name'] = msa['cbsa_code'].map(cbsa_names)

    return msa


def compute_mdi(msa):
    """Compute the Medical Dependence Index."""
    # Filter qualifying MSAs
    print(f'Total MSAs with hospital data: {len(msa)}')

    msa = msa[msa['pop_msa'].notna() & (msa['pop_msa'] >= MIN_MSA_POP)].copy()
    print(f'After min pop ({MIN_MSA_POP:,}): {len(msa)}')

    msa = msa[msa['pop_msa'] <= MAX_MSA_POP].copy()
    print(f'After max pop ({MAX_MSA_POP:,}): {len(msa)}')

    msa = msa[msa['total_beds'] >= MIN_BEDS].copy()
    print(f'After min beds ({MIN_BEDS}): {len(msa)}')

    msa = msa[msa['hospital_emp_share'].notna()].copy()
    print(f'After requiring employment data: {len(msa)}')

    if msa.empty:
        print('ERROR: No qualifying MSAs')
        return msa

    # Component A: Hospital Employment Intensity
    a_raw = msa['hospital_emp_share']
    a_min = a_raw.min()
    a_95 = a_raw.quantile(0.95)
    msa['component_a'] = ((a_raw - a_min) / (a_95 - a_min)).clip(0, 1)

    # Component B: Government Payer Intensity
    b_raw = msa['govt_payer_share']
    b_min = b_raw.min()
    b_95 = b_raw.quantile(0.95)
    msa['component_b'] = ((b_raw - b_min) / (b_95 - b_min)).clip(0, 1)

    # Component C: Hospital Payroll Dominance
    c_raw = msa['hospital_payroll_share'].fillna(msa['hospital_emp_share'])
    c_min = c_raw.min()
    c_95 = c_raw.quantile(0.95)
    msa['component_c'] = ((c_raw - c_min) / (c_95 - c_min)).clip(0, 1)

    # Composite MDI
    msa['mdi'] = (
        WEIGHT_A * msa['component_a'] +
        WEIGHT_B * msa['component_b'] +
        WEIGHT_C * msa['component_c']
    )

    # Rank
    msa = msa.sort_values('mdi', ascending=False).reset_index(drop=True)
    msa['mdi_rank'] = range(1, len(msa) + 1)

    return msa


def build_rankings_json(msa):
    """Build hub_rankings.json."""
    records = []
    for _, row in msa.iterrows():
        records.append({
            'cbsa_code': row['cbsa_code'],
            'cbsa_name': row.get('cbsa_name', ''),
            'mdi': round(row['mdi'], 4),
            'mdi_rank': int(row['mdi_rank']),
            'component_a_hospital_emp_share': round(row.get('hospital_emp_share', 0), 4),
            'component_b_govt_payer_share': round(row.get('govt_payer_share', 0), 4),
            'component_c_payroll_dominance': round(row.get('hospital_payroll_share', 0) if pd.notna(row.get('hospital_payroll_share')) else 0, 4),
            'pop_msa': int(row.get('pop_msa', 0)),
            'pop_catchment': None,  # Filled by catchment computation
            'catchment_radius_miles': None,
            'total_beds': int(row.get('total_beds', 0)),
            'num_hospitals': int(row.get('num_hospitals', 0)),
            'largest_hospital': row.get('largest_hospital', ''),
            'pct_65_plus_msa': round(row.get('pct_65_plus_msa', 0), 4),
            'pct_65_plus_catchment': None,
            'hospital_employment': int(row.get('hospital_employment', 0)) if pd.notna(row.get('hospital_employment')) else None,
            'total_employment': int(row.get('total_employment', 0)) if pd.notna(row.get('total_employment')) else None,
            'avg_hospital_wage_weekly': round(row.get('avg_hospital_wage', 0), 0) if pd.notna(row.get('avg_hospital_wage')) else None,
            'hub_lat': round(row.get('hub_lat', 0), 4),
            'hub_lon': round(row.get('hub_lon', 0), 4),
        })

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(records, f, indent=2)
    print(f'Saved {len(records)} hub rankings to {OUTPUT_FILE}')

    return records


def compute_and_rank():
    """Main entry point."""
    hospitals, payer, employment, population = load_data()
    hosp = join_hospitals_to_cbsa(hospitals, payer, employment)
    msa = compute_msa_metrics(hosp, employment, population)
    msa = compute_mdi(msa)

    if msa.empty:
        return msa, []

    rankings = build_rankings_json(msa)

    # Validation
    print(f'\n=== Validation ===')
    print(f'Qualifying MSA hubs: {len(msa)}')
    print(f'MDI range: {msa["mdi"].min():.4f} — {msa["mdi"].max():.4f}')
    print(f'\nTop 20 medical hubs:')
    for _, row in msa.head(20).iterrows():
        print(f'  #{int(row["mdi_rank"]):3d}  MDI={row["mdi"]:.3f}  {row.get("cbsa_name", row["cbsa_code"])}'
              f'  (beds={int(row["total_beds"])}, emp_share={row["hospital_emp_share"]:.3f})')

    # Check for Rochester MN
    rochester = msa[msa['cbsa_code'] == '40340']
    if not rochester.empty:
        rank = int(rochester.iloc[0]['mdi_rank'])
        print(f'\n✓ Rochester, MN (Mayo Clinic) is ranked #{rank}')
        if rank > 10:
            print('  ⚠ WARNING: Rochester should be top 10. Check computation.')
    else:
        print('\n⚠ WARNING: Rochester, MN (CBSA 40340) not found in results')

    return msa, rankings


if __name__ == '__main__':
    compute_and_rank()
