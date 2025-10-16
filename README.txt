
African Critical Minerals App - sample data package
-----------------------------------------------
This package contains a small, realistic dataset assembled from public authoritative sources (USGS MCS 2024/2025 & BGS).
Files:
- data/countries.csv
- data/minerals.csv
- data/sites.csv
- data/production_stats.csv
- data/users.csv
- data/roles.csv
- assets/ (empty for now; you can drop an africa_map.png or logo there)
- SOURCES.txt  (lists the primary sources and notes)

I used USGS MCS commodity tables for production numbers (cobalt, lithium, graphite, manganese) and BGS World Mineral Production for cross-checks.
Coordinates for 'sites' are approximate and meant for demo mapping. Replace them with accurate locations from national datasets before any operational use.

Next steps I can do for you (pick one):
- Wire these CSVs into a Flask web app (app.py) with interactive charts + map.
- Build a Streamlit or Dash app to serve dashboards quickly (recommended for prototyping).
- Add real geospatial site points from USGS or national open datasets and produce an interactive Folium map.

Tell me which of the above you'd like me to build next; I can generate the web app code and a runnable ZIP.
