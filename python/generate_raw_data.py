"""
generate_raw_data.py
Creates the SIMULATED raw programme monitoring extracts in data/raw (seeded, so the output is identical every run).

The simulation places 1,000 households in 20 settlement clusters across four ASAL counties,
16 distribution sites (two suspended), ten months of distributions and household ration receipts.
Supply breaks, distance effects and data errors (duplicates, blanks, swapped quantities, bad
coordinates) are built in on purpose so the cleaning and analysis steps have real work to do.
Coordinates are approximate and for illustration only.

Run first:  python generate_raw_data.py
"""
import numpy as np, pandas as pd, math
from pathlib import Path

rng = np.random.default_rng(2026)
OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

COUNTIES = {
    "Turkana": dict(code="TUR", origin=(3.12, 35.60),
        subs=["Turkana Central", "Turkana West", "Loima", "Turkana South", "Turkana North"],
        clusters=[(0, 0), (14, 5), (-12, 9), (5, -17), (-4, -9)],
        sites=[(1, 1, "Active", 10), (15, 4, "Suspended", 5), (-11, 10, "Active", 5), (11, -17, "Active", 5)]),
    "Marsabit": dict(code="MAR", origin=(2.33, 37.99),
        subs=["Saku", "Laisamis", "Moyale", "North Horr", "North Horr"],
        clusters=[(0, 0), (-13, 8), (12, 10), (4, -15), (-10, -8)],
        sites=[(0.5, 1, "Active", 5), (-12, 9, "Active", 5), (11.5, 11, "Suspended", 5), (-3, -16, "Active", 5)]),
    "Isiolo": dict(code="ISI", origin=(0.35, 37.58),
        subs=["Isiolo North", "Garbatulla", "Merti", "Isiolo South", "Isiolo North"],
        clusters=[(0, 0), (10, 7), (-9, 6), (3, -11), (-5, -5)],
        sites=[(0.5, 0.5, "Active", 5), (10.5, 7, "Active", 5), (-8.5, 6.5, "Active", 5), (3, -11, "Active", 5)]),
    "Garissa": dict(code="GAR", origin=(-0.45, 39.65),
        subs=["Garissa Township", "Balambala", "Lagdera", "Dadaab", "Fafi"],
        clusters=[(0, 0), (14, -6), (-12, -8), (5, 16), (-6, 12)],
        sites=[(1, 0.5, "Active", 10), (13, -6.5, "Active", 10), (-11, -7, "Active", 10), (12, 16, "Active", 10)]),
}

def km_to_ll(origin, dx, dy):
    lat0, lon0 = origin
    dlat = dy / 111.19
    dlon = dx / (111.19 * math.cos(math.radians(lat0)))
    return lat0 + dlat, lon0 + dlon

def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))

FIRST = ["Ekai", "Naomi", "Lokiru", "Akai", "Amina", "Hussein", "Halima", "Abdi", "Fatuma", "Wario", "Jattani",
         "Dida", "Galgalo", "Nasra", "Mohamed", "Hawa", "Ibrahim", "Lokwang", "Achuka", "Ibrae", "Sadia", "Yusuf",
         "Nakiru", "Epur", "Lomuria", "Kinyua", "Rukia", "Guyo", "Boru", "Samira"]
SECOND = ["Ekiru", "Lowoi", "Abdille", "Hassan", "Adan", "Duba", "Ali", "Jillo", "Noor", "Ekeno", "Lokoel", "Ayub",
          "Gedi", "Maalim", "Orto", "Aden", "Nyang", "Ewoi", "Kamau", "Roba", "Diba", "Lemuya", "Omar", "Sora",
          "Ikal", "Barre", "Kurewa", "Mursal", "Lomong", "Hirbo"]

# ---------- sites ----------
site_rows = []
sid = 1
for cname, c in COUNTIES.items():
    for i, (dx, dy, status, rad) in enumerate(c["sites"], start=1):
        lat, lon = km_to_ll(c["origin"], dx, dy)
        site_rows.append(dict(site_id=f"S{sid:02d}", site_name=f"{cname} Distribution Point {i}", county=cname,
                              latitude=round(lat, 5), longitude=round(lon, 5), operational_status=status,
                              max_radius_km=rad))
        sid += 1
sites = pd.DataFrame(site_rows)

# ---------- households ----------
hh_rows = []
n = 1
for cname, c in COUNTIES.items():
    for ci, (cx, cy) in enumerate(c["clusters"], start=1):
        cid = f"{c['code']}-S{ci}"
        names = set()
        for _ in range(50):
            while True:
                nm = f"{rng.choice(FIRST)} {rng.choice(SECOND)}"
                if nm not in names:
                    names.add(nm)
                    break
            x = cx + rng.normal(0, 2.0)
            y = cy + rng.normal(0, 2.0)
            lat, lon = km_to_ll(c["origin"], x, y)
            hh_rows.append(dict(household_id=f"HH{n:04d}", head_name=nm, county=cname, subcounty=c["subs"][ci - 1],
                                settlement_cluster=cid, household_size=int(np.clip(rng.poisson(5), 2, 10)),
                                vulnerability_score=int(np.clip(rng.normal(62, 15), 10, 100)),
                                target_rations=10,
                                enrol_date=(pd.Timestamp("2025-09-01") + pd.Timedelta(days=int(rng.integers(0, 120)))).date().isoformat(),
                                latitude=round(lat, 5), longitude=round(lon, 5)))
            n += 1
hh = pd.DataFrame(hh_rows)

# nearest operational site and distance (truth used for simulation)
op = sites[sites.operational_status == "Active"].reset_index(drop=True)
D = np.stack([haversine(hh.latitude.values, hh.longitude.values, r.latitude, r.longitude) for r in op.itertuples()], axis=1)
hh["tmp_site"] = op.site_id.values[D.argmin(axis=1)]
hh["tmp_dist"] = D.min(axis=1)

# ---------- supply fulfilment ----------
months = pd.date_range("2026-01-01", periods=10, freq="MS")
KG = {"Cereal": 50, "Pulses": 10, "Vegetable Oil": 3, "Super Cereal CSB++": 8}
fulf = {c: {m: float(np.clip(rng.normal(0.94, 0.035), 0.8, 1.0)) for m in months} for c in COUNTIES}
fulf["Marsabit"][months[2]] = 0.60
fulf["Marsabit"][months[3]] = 0.55
fulf["Turkana"][months[5]] = 0.68
fulf["Garissa"][months[7]] = 0.72

dist_rows = []
did = 1
assigned = hh.groupby("tmp_site").size().to_dict()
for s in op.itertuples():
    nhh = assigned.get(s.site_id, 0)
    for m in months:
        for com, kg in KG.items():
            planned = nhh * kg / 1000
            f = fulf[s.county][m] + rng.normal(0, 0.02)
            if com == "Super Cereal CSB++" and m.month in (9, 10):
                f = 0.62 + rng.normal(0, 0.03)
            if com == "Pulses" and m.month == 10:
                f = min(f, 0.80)
            f = float(np.clip(f, 0.3, 1.0))
            disp = planned * f
            rec = disp * rng.uniform(0.96, 1.0)
            day = int(rng.integers(5, 21))
            dist_rows.append(dict(dist_id=f"D{did:05d}", site_id=s.site_id,
                                  dist_date=(m + pd.Timedelta(days=day - 1)).date().isoformat(), commodity=com,
                                  qty_planned_mt=round(planned, 3), qty_dispatched_mt=round(disp, 3),
                                  qty_received_mt=round(rec, 3)))
            did += 1
dist = pd.DataFrame(dist_rows)

# ---------- household receipts ----------
rec_rows = []
for r in hh.itertuples():
    df = 0.97 if r.tmp_dist <= 5 else (0.80 if r.tmp_dist <= 10 else 0.55)
    for m in months:
        p = min(1.0, fulf[r.county][m] + 0.04) * df
        rec_rows.append(dict(household_id=r.household_id, ration_month=m.date().isoformat(),
                             rations_received=int(rng.random() < p)))
rec = pd.DataFrame(rec_rows)

# ---------- inject dirt into the raw files ----------
raw = hh.drop(columns=["tmp_site", "tmp_dist"]).copy()
dups = raw.sample(40, random_state=7).copy()
dups["household_id"] = [f"HH{1001 + i:04d}" for i in range(len(dups))]
dups["head_name"] = [x.upper() if i % 2 == 0 else x + " " for i, x in enumerate(dups.head_name)]
raw = pd.concat([raw, dups], ignore_index=True)
idx = rng.permutation(len(raw))
raw.loc[idx[:38], "vulnerability_score"] = np.nan
raw.loc[idx[38:60], "subcounty"] = np.nan
variants = {"Turkana": "turkana", "Marsabit": "MARSABIT", "Isiolo": "Isiolo ", "Garissa": "garissa"}
for j in idx[60:74]:
    raw.loc[j, "county"] = variants[raw.loc[j, "county"].strip()]
raw.loc[idx[74:80], ["latitude", "longitude"]] = np.nan
raw.loc[idx[80:83], ["latitude", "longitude"]] = 0.0
raw = raw.sample(frac=1, random_state=3).reset_index(drop=True)

rd = dist.copy()
i2 = rng.permutation(len(rd))
rd.loc[i2[:8], ["qty_dispatched_mt", "qty_received_mt"]] = rd.loc[i2[:8], ["qty_received_mt", "qty_dispatched_mt"]].values
rd.loc[i2[8:14], "qty_dispatched_mt"] = np.nan
rd = pd.concat([rd, rd.loc[i2[14:19]]], ignore_index=True)
bad = rd.loc[i2[19:23]].copy()
bad["site_id"] = "S99"
bad["dist_id"] = [f"D9{k:04d}" for k in range(len(bad))]
rd = pd.concat([rd, bad], ignore_index=True)

raw.to_csv(OUT / "raw_beneficiaries.csv", index=False)
rd.to_csv(OUT / "raw_distributions.csv", index=False)
rec.to_csv(OUT / "raw_ration_receipts.csv", index=False)
sites.to_csv(OUT / "raw_sites.csv", index=False)
print(len(raw), len(rd), len(rec), len(sites))
