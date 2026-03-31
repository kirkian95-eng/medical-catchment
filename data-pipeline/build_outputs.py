#!/usr/bin/env python3
"""
Orchestrator: runs the full data pipeline.
  1. Fetch CMS hospital inventory
  2. Fetch CMS payer mix / Medicare utilization
  3. Fetch BLS QCEW employment data
  4. Fetch Census population data
  5. Fetch county geometries
  6. Compute Medical Dependence Index
  7. Compute catchment areas
  8. Copy outputs for frontend
"""
import os
import sys
import shutil
import time

OUTPUT_DIR = 'output'
FRONTEND_DATA_DIR = os.path.join('..', 'frontend', 'public', 'data')


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    start = time.time()

    # === Step 1: Hospital Inventory ===
    print('\n' + '='*60)
    print('STEP 1: Fetch CMS Hospital Inventory')
    print('='*60)
    from fetch_hospitals import fetch_and_process as fetch_hospitals
    hospitals_df = fetch_hospitals()
    if hospitals_df is None or hospitals_df.empty:
        print('FATAL: No hospital data. Aborting.')
        sys.exit(1)

    # === Step 2: Payer Mix ===
    print('\n' + '='*60)
    print('STEP 2: Fetch CMS Payer Mix / Medicare Utilization')
    print('='*60)
    from fetch_cost_reports import fetch_and_process as fetch_payer
    payer_df = fetch_payer(hospitals_df)

    # === Step 3: Employment ===
    print('\n' + '='*60)
    print('STEP 3: Fetch BLS QCEW Employment Data')
    print('='*60)
    from fetch_employment import fetch_and_process as fetch_employment
    employment_df = fetch_employment()

    # === Step 4: Population ===
    print('\n' + '='*60)
    print('STEP 4: Fetch Census Population Data')
    print('='*60)
    from fetch_population import fetch_and_process as fetch_population
    population_df = fetch_population()

    # === Step 5: Geometries ===
    print('\n' + '='*60)
    print('STEP 5: Fetch County Geometries')
    print('='*60)
    from fetch_geometries import fetch_and_process as fetch_geometries
    counties_gdf, interstates_gdf = fetch_geometries()

    # === Step 6: Compute MDI ===
    print('\n' + '='*60)
    print('STEP 6: Compute Medical Dependence Index')
    print('='*60)
    from compute_dependence import compute_and_rank
    msa_df, rankings = compute_and_rank()
    if not rankings:
        print('FATAL: No qualifying hubs. Aborting.')
        sys.exit(1)

    # === Step 7: Compute Catchments ===
    print('\n' + '='*60)
    print('STEP 7: Compute Catchment Areas')
    print('='*60)
    from compute_catchments import compute_catchments
    compute_catchments()

    # === Step 8: Copy to frontend ===
    print('\n' + '='*60)
    print('STEP 8: Copy outputs to frontend')
    print('='*60)
    copy_to_frontend()

    elapsed = time.time() - start
    print(f'\n{"="*60}')
    print(f'PIPELINE COMPLETE in {elapsed/60:.1f} minutes')
    print(f'{"="*60}')

    # Final validation summary
    print_validation_summary()


def copy_to_frontend():
    """Copy data files to frontend public directory."""
    os.makedirs(FRONTEND_DATA_DIR, exist_ok=True)
    hubs_dest = os.path.join(FRONTEND_DATA_DIR, 'hubs')
    os.makedirs(hubs_dest, exist_ok=True)

    files_to_copy = [
        'hub_rankings.json',
        'national_catchments.json',
        'interstates.geojson',
    ]

    for fname in files_to_copy:
        src = os.path.join(OUTPUT_DIR, fname)
        dst = os.path.join(FRONTEND_DATA_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            size = os.path.getsize(dst) / 1024 / 1024
            print(f'  Copied {fname} ({size:.1f} MB)')

    # Copy hub detail files
    hubs_src = os.path.join(OUTPUT_DIR, 'hubs')
    if os.path.isdir(hubs_src):
        count = 0
        for fname in os.listdir(hubs_src):
            if fname.endswith('.json'):
                shutil.copy2(os.path.join(hubs_src, fname), os.path.join(hubs_dest, fname))
                count += 1
        print(f'  Copied {count} hub detail files')


def print_validation_summary():
    """Print a summary of all output files."""
    import json

    print('\n=== OUTPUT FILES ===')
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for f in sorted(files):
            if f.endswith(('.json', '.geojson', '.csv')):
                path = os.path.join(root, f)
                size = os.path.getsize(path) / 1024
                unit = 'KB'
                if size > 1024:
                    size /= 1024
                    unit = 'MB'
                rel = os.path.relpath(path, OUTPUT_DIR)
                print(f'  {rel:40s} {size:6.1f} {unit}')

    # Quick data check
    rankings_file = os.path.join(OUTPUT_DIR, 'hub_rankings.json')
    if os.path.exists(rankings_file):
        with open(rankings_file) as f:
            rankings = json.load(f)
        print(f'\n=== FINAL RESULTS ===')
        print(f'Total medical hubs: {len(rankings)}')
        if rankings:
            print(f'Top 5:')
            for r in rankings[:5]:
                pop = f"{r.get('pop_catchment', 0):,}" if r.get('pop_catchment') else 'N/A'
                print(f"  #{r['mdi_rank']} {r['cbsa_name']} — MDI {r['mdi']:.3f}, "
                      f"beds {r['total_beds']}, catchment pop {pop}")


if __name__ == '__main__':
    main()
