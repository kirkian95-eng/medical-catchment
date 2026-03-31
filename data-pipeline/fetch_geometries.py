"""
Fetch and simplify county boundary geometries from TIGER/Line.
Also fetch Interstate highway centerlines for context.
Output: output/counties.geojson, output/interstates.geojson
"""
import os
import requests
import geopandas as gpd
from shapely.geometry import shape

OUTPUT_DIR = 'output'
COUNTY_URL = 'https://www2.census.gov/geo/tiger/TIGER2022/COUNTY/tl_2022_us_county.zip'
ROADS_URL = 'https://www2.census.gov/geo/tiger/TIGER2022/PRIMARYROADS/tl_2022_us_primaryroads.zip'

# Contiguous US state FIPS
VALID_STATE_FIPS = {
    '01','04','05','06','08','09','10','11','12','13','16','17','18',
    '19','20','21','22','23','24','25','26','27','28','29','30','31','32','33',
    '34','35','36','37','38','39','40','41','42','44','45','46','47','48','49',
    '50','51','53','54','55','56'
}


def download_file(url, local_path):
    """Download a file with progress reporting."""
    if os.path.exists(local_path):
        print(f'  Using cached: {local_path}')
        return
    print(f'  Downloading {url}...')
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(local_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=1024*1024):
            f.write(chunk)
    print(f'  Saved to {local_path}')


def fetch_counties():
    """Download and simplify county boundaries."""
    output_file = os.path.join(OUTPUT_DIR, 'counties.geojson')
    if os.path.exists(output_file):
        print(f'Using cached counties: {output_file}')
        return gpd.read_file(output_file)

    zip_path = os.path.join(OUTPUT_DIR, 'tl_2022_us_county.zip')
    download_file(COUNTY_URL, zip_path)

    print('Reading county shapefile...')
    gdf = gpd.read_file(f'zip://{zip_path}')

    # Filter to contiguous US
    gdf = gdf[gdf['STATEFP'].isin(VALID_STATE_FIPS)].copy()
    print(f'Counties in contiguous US: {len(gdf)}')

    # Keep only needed columns
    gdf = gdf[['GEOID', 'STATEFP', 'NAME', 'geometry']].copy()
    gdf = gdf.rename(columns={'GEOID': 'county_fips', 'STATEFP': 'state_fips', 'NAME': 'county_name'})

    # Simplify geometry (target ~5MB)
    # County geometries are much simpler than tract-level, use moderate tolerance
    gdf = gdf.to_crs('EPSG:5070')  # Albers Equal Area for simplification
    gdf['geometry'] = gdf.geometry.simplify(tolerance=500)  # 500m tolerance
    gdf = gdf.to_crs('EPSG:4326')  # Back to WGS84

    # Compute centroids (in WGS84)
    gdf['centroid_lon'] = gdf.geometry.centroid.x
    gdf['centroid_lat'] = gdf.geometry.centroid.y

    gdf.to_file(output_file, driver='GeoJSON')
    size_mb = os.path.getsize(output_file) / 1024 / 1024
    print(f'Saved counties to {output_file} ({size_mb:.1f} MB)')

    return gdf


def fetch_interstates():
    """Download and filter Interstate highways."""
    output_file = os.path.join(OUTPUT_DIR, 'interstates.geojson')
    if os.path.exists(output_file):
        print(f'Using cached interstates: {output_file}')
        return gpd.read_file(output_file)

    zip_path = os.path.join(OUTPUT_DIR, 'tl_2022_us_primaryroads.zip')
    download_file(ROADS_URL, zip_path)

    print('Reading primary roads...')
    gdf = gpd.read_file(f'zip://{zip_path}')

    # Filter to Interstate highways (MTFCC = S1100)
    gdf = gdf[gdf['MTFCC'] == 'S1100'].copy()
    print(f'Interstate highway segments: {len(gdf)}')

    # Simplify
    gdf = gdf.to_crs('EPSG:5070')
    gdf['geometry'] = gdf.geometry.simplify(tolerance=200)
    gdf = gdf.to_crs('EPSG:4326')

    # Keep minimal columns
    gdf = gdf[['FULLNAME', 'geometry']].copy()
    gdf = gdf.rename(columns={'FULLNAME': 'name'})

    gdf.to_file(output_file, driver='GeoJSON')
    size_mb = os.path.getsize(output_file) / 1024 / 1024
    print(f'Saved interstates to {output_file} ({size_mb:.1f} MB)')

    return gdf


def fetch_and_process():
    """Main entry point."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    counties = fetch_counties()
    interstates = fetch_interstates()

    print(f'\n=== Validation ===')
    print(f'Total counties: {len(counties)}')
    print(f'Interstate segments: {len(interstates)}')

    return counties, interstates


if __name__ == '__main__':
    fetch_and_process()
