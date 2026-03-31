# American Medical Catchment Map

Static-build web application: Python data pipeline (CMS + BLS + Census → Medical Dependence Index → JSON/GeoJSON) + React frontend (MapLibre GL JS interactive map).

## Stack
- **Pipeline:** Python 3, pandas, geopandas, numpy, scipy, scikit-learn, shapely
- **Frontend:** React 18, Vite 5, MapLibre GL JS, react-map-gl, Tailwind CSS 3.4, react-window, d3
- **Data Sources:** CMS Hospital General Info + POS (beds) + Medicare Utilization, BLS QCEW, Census ACS 2022, TIGER/Line 2022, CBSA 2023

## Commands
- `cd data-pipeline && python3 build_outputs.py` — run full pipeline (fetch → compute → output)
- `cd data-pipeline && python3 fetch_hospitals.py` — just hospital inventory
- `cd frontend && npm run dev` — dev server (port 5006)
- `cd frontend && npx vite build` — production build

## Architecture
```
CMS data + BLS QCEW + Census API → python pipeline → static JSON/GeoJSON → React frontend (MapLibre)
```

Pipeline outputs go to `data-pipeline/output/` and are copied to `frontend/public/data/` by `build_outputs.py`.

## Design
Data journalism aesthetic (NYT Upshot / ProPublica). Dark sidebar, warm map palette (YlOrRd). DM Serif Display headers, Source Sans 3 body, JetBrains Mono numbers. Map is the hero element.
