"""
walk_less_analysis.py
Site access analysis: how far is each household from the nearest active
distribution site, and where should new sites go to close the gaps?

Distances use the haversine formula on household and site coordinates, so no GIS licence is needed.
The same 5 km and 10 km bands can be reproduced in QGIS with buffers around tbl_Sites_GIS.

Run:  python walk_less_analysis.py     (after clean_meal_data.py)
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
WALK_KM = 5.0
FAR_KM = 10.0
MAX_NEW_SITES = 5


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((np.radians(lon2) - np.radians(lon1)) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def band(d):
    return np.where(d <= WALK_KM, "Within 5 km", np.where(d <= FAR_KM, "5 to 10 km", "Over 10 km"))


def nearest(hh, site_df):
    D = np.stack([haversine(hh.latitude.values, hh.longitude.values, s.latitude, s.longitude) for s in site_df.itertuples()], axis=1)
    return site_df.site_id.values[D.argmin(axis=1)], D.min(axis=1)


hh = pd.read_csv(CLEAN / "beneficiaries.csv")
sites = pd.read_csv(CLEAN / "sites.csv")
active = sites[sites.operational_status == "Active"]

# 1. Current coverage against active sites
hh["nearest_site_id"], hh["nearest_site_km"] = nearest(hh, active)
hh["nearest_site_km"] = hh["nearest_site_km"].round(2)
hh["coverage_band"] = band(hh["nearest_site_km"])

# 2. What if the suspended sites were reopened?
_, d_all = nearest(hh, sites)
reopen_pct = float((d_all <= WALK_KM).mean() * 100)

# 3. Settlement cluster summary
cl = hh.groupby(["settlement_cluster", "county"]).agg(
    households=("household_id", "count"),
    centroid_lat=("latitude", "mean"),
    centroid_lon=("longitude", "mean"),
    median_walk_km=("nearest_site_km", "median"),
    max_walk_km=("nearest_site_km", "max"),
    pct_within_5km=("nearest_site_km", lambda s: round((s <= WALK_KM).mean() * 100, 1)),
    pct_over_10km=("nearest_site_km", lambda s: round((s > FAR_KM).mean() * 100, 1)),
).reset_index().round(4)
cl = cl.sort_values("median_walk_km", ascending=False)

# 4. Greedy site placement. Step one assumes the suspended sites are reopened, then each new site goes
# where it covers the most households that are still outside 5 km.
covered = (d_all <= WALK_KM).copy()
cand = hh[["latitude", "longitude", "county"]].reset_index(drop=True)
Dc = np.stack([haversine(hh.latitude.values, hh.longitude.values, r.latitude, r.longitude) for r in cand.itertuples()], axis=1) <= WALK_KM
recs = []
for k in range(1, MAX_NEW_SITES + 1):
    gain = (Dc & ~covered[:, None]).sum(axis=0)
    j = int(gain.argmax())
    if gain[j] == 0:
        break
    members = Dc[:, j] & ~covered
    # centre the site on the households it will serve
    lat, lon = hh.loc[members, "latitude"].mean(), hh.loc[members, "longitude"].mean()
    # coverage is measured from the final site position, not from the candidate household it was found at
    within = haversine(hh.latitude.values, hh.longitude.values, lat, lon) <= WALK_KM
    newly = int((within & ~covered).sum())
    covered = covered | within
    recs.append(dict(rank=k, county=cand.loc[j, "county"], latitude=round(lat, 5), longitude=round(lon, 5),
                     new_households_covered=newly, cumulative_coverage_pct=round(covered.mean() * 100, 1)))
rec_df = pd.DataFrame(recs)

# 5. Save
hh_out = hh[["household_id", "county", "subcounty", "settlement_cluster", "latitude", "longitude", "vulnerability_score",
             "nearest_site_id", "nearest_site_km", "coverage_band"]]
hh_out.to_csv(CLEAN / "household_coverage.csv", index=False)
cl.to_csv(CLEAN / "cluster_coverage.csv", index=False)
rec_df.to_csv(CLEAN / "recommended_sites.csv", index=False)

cur = float((hh.nearest_site_km <= WALK_KM).mean() * 100)
summary = dict(
    households=len(hh), within_5km_pct=round(cur, 1),
    between_5_10_pct=round(float(((hh.nearest_site_km > WALK_KM) & (hh.nearest_site_km <= FAR_KM)).mean() * 100), 1),
    over_10km_pct=round(float((hh.nearest_site_km > FAR_KM).mean() * 100), 1),
    median_walk_km=round(float(hh.nearest_site_km.median()), 2),
    reopen_suspended_within_5km_pct=round(reopen_pct, 1),
)
(CLEAN / "walk_less_summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
print(hh.groupby("county").nearest_site_km.agg(["median", lambda s: (s <= 5).mean() * 100, lambda s: (s > 10).mean() * 100]).round(1))
print(rec_df.to_string(index=False))
print(cl[["settlement_cluster", "households", "median_walk_km", "pct_within_5km"]].to_string(index=False))
