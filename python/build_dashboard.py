"""
build_dashboard.py
Packs the cleaned data and query results into one self contained HTML dashboard
(dashboard/monitoring_dashboard.html). Open the file in any browser, no server needed.
Run last: after clean_meal_data.py, walk_less_analysis.py and build_database.py.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
Q = CLEAN / "query_results"
COUNTIES = ["Turkana", "Marsabit", "Isiolo", "Garissa"]
COMMS = ["Cereal", "Pulses", "Vegetable Oil", "Super Cereal CSB++"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
BANDS = ["Within 5 km", "5 to 10 km", "Over 10 km"]


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((np.radians(lon2) - np.radians(lon1)) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


hh = pd.read_csv(CLEAN / "household_coverage.csv")
sites = pd.read_csv(CLEAN / "sites.csv")
dist = pd.read_csv(CLEAN / "distributions.csv").merge(sites[["site_id", "county"]], on="site_id")
dist["m"] = dist["dist_date"].str[5:7].astype(int) - 1
q1, q2, q3, q4 = (pd.read_csv(Q / f"Q{i}.csv") for i in (1, 2, 3, 4))
cl = pd.read_csv(CLEAN / "cluster_coverage.csv")
recs = pd.read_csv(CLEAN / "recommended_sites.csv")
summ = json.loads((CLEAN / "walk_less_summary.json").read_text())
dq = pd.read_csv(CLEAN / "data_quality_log.csv")

# --- headline numbers
planned, received = dist.qty_planned_mt.sum(), dist.qty_received_mt.sum()
delivered = int(q3.households_reached.sum())
target = int(q3.households_targeted.sum())
served = hh.groupby("nearest_site_id").size().to_dict()

# --- scenarios by county: current, reopen suspended sites, reopen and add recommended sites
def within5(df, site_df):
    d = np.stack([haversine(df.latitude.values, df.longitude.values, s.latitude, s.longitude) for s in site_df.itertuples()], axis=1).min(axis=1)
    return d <= 5

rec_pts = recs.rename(columns={"latitude": "latitude", "longitude": "longitude"})[["latitude", "longitude"]]
all_pts = pd.concat([sites[["latitude", "longitude"]], rec_pts], ignore_index=True)
active = sites[sites.operational_status == "Active"]
scen = {}
for name, sub in [("All", hh)] + [(c, hh[hh.county == c]) for c in COUNTIES]:
    scen[name] = [round(float(within5(sub, active).mean() * 100), 1),
                  round(float(within5(sub, sites).mean() * 100), 1),
                  round(float(within5(sub, all_pts).mean() * 100), 1)]

# --- findings sentences (no dashes in the copy)
band = q4.set_index("coverage_band").reach_rate_pct
cm = q1.copy()
worst = cm.sort_values("completion_rate_pct").head(3)
mon = {"2026-03": "March", "2026-04": "April", "2026-06": "June", "2026-08": "August"}
sc = dist[dist.commodity == "Super Cereal CSB++"].groupby("m")[["qty_planned_mt", "qty_received_mt"]].sum()
sc_pct = (100 * sc.qty_received_mt / sc.qty_planned_mt).round(1)
findings = [
    f"Households received {delivered:,} of {target:,} targeted monthly rations ({delivered / target * 100:.1f} percent).",
    f"Distance drives missed rations: households within 5 km were reached {band['Within 5 km']:.1f} percent of the time, "
    f"against {band['Over 10 km']:.1f} percent for households over 10 km away.",
    f"Supply fell short of plan by {100 - received / planned * 100:.1f} percent overall. Super Cereal dropped to "
    f"{sc_pct[8]:.1f} and {sc_pct[9]:.1f} percent of plan in September and October.",
    f"Only {summ['within_5km_pct']:.1f} percent of households live within 5 km of an active site. Reopening the two suspended sites "
    f"lifts this to {summ['reopen_suspended_within_5km_pct']:.1f} percent, and five new sites reach {scen['All'][2]:.1f} percent.",
]

# --- data quality strip
def dqn(check_text):
    return int(dq[dq.check.str.contains(check_text, regex=False)].rows_affected.sum())

dq_items = [
    ["Duplicate registrations removed", dqn("duplicate registration")],
    ["Missing vulnerability scores filled", dqn("missing vulnerability")],
    ["Missing or invalid coordinates fixed", dqn("coordinates")],
    ["Missing subcounties filled", dqn("missing subcounty")],
    ["Distribution lines with swapped quantities", dqn("received quantity above")],
    ["Distribution lines with unknown site", dqn("site id not in")],
]

data = dict(
    months=MONTHS, counties=COUNTIES, commodities=COMMS, bands=BANDS,
    kpi=dict(households=int(len(hh)), delivered=delivered, target=target, planned=round(planned, 1), received=round(received, 1),
             fulfil=round(received / planned * 100, 1), sites=int(len(sites)), active=int((sites.operational_status == "Active").sum()),
             within5=summ["within_5km_pct"], mid=summ["between_5_10_pct"], over10=summ["over_10km_pct"], median=summ["median_walk_km"]),
    reach=[int(x) for x in q3.households_reached],
    cm={c: dict(planned=[round(float(x), 2) for x in q1[q1.county == c].planned_mt],
                received=[round(float(x), 2) for x in q1[q1.county == c].received_mt],
                pct=[float(x) for x in q1[q1.county == c].completion_rate_pct]) for c in COUNTIES},
    cc=[dict(county=r.county, commodity=r.commodity, planned=float(r.planned_mt), received=float(r.received_mt),
             variance=round(float(r.received_mt - r.planned_mt), 1), pct=float(r.completion_rate_pct)) for r in q2.itertuples()],
    cmm={c: [round(float(100 * g.qty_received_mt.sum() / g.qty_planned_mt.sum()), 1) for _, g in
             dist[dist.commodity == c].groupby("m")] for c in COMMS},
    reachBand=[[b, float(band[b])] for b in BANDS],
    sites=[dict(id=s.site_id, name=s.site_name, county=s.county, lat=s.latitude, lon=s.longitude, status=s.operational_status,
                radius=s.max_radius_km, served=int(served.get(s.site_id, 0))) for s in sites.itertuples()],
    hh=[[round(r.latitude, 4), round(r.longitude, 4), float(r.nearest_site_km), BANDS.index(r.coverage_band),
         r.settlement_cluster] for r in hh.itertuples()],
    clusters=[dict(id=r.settlement_cluster, county=r.county, n=int(r.households), median=float(r.median_walk_km),
                   within5=float(r.pct_within_5km), over10=float(r.pct_over_10km)) for r in cl.itertuples()],
    recs=[dict(rank=int(r["rank"]), county=r.county, lat=r.latitude, lon=r.longitude, n=int(r.new_households_covered),
               cum=float(r.cumulative_coverage_pct)) for _, r in recs.iterrows()],
    scen=scen, findings=findings, dq=dq_items, rawRegs=int(len(hh) + dqn("duplicate registration")),
)

tpl = (ROOT / "dashboard" / "dashboard_template.html").read_text()
html = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")))
(ROOT / "dashboard" / "monitoring_dashboard.html").write_text(html)
print("dashboard written", len(html) // 1024, "KB")
print(findings)
print(scen)
