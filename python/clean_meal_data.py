"""
clean_meal_data.py
Data quality and validation step for the "Who Is Food Aid Missing?" project.

Reads the raw programme monitoring extracts, fixes or flags every issue it finds, and writes
analysis ready files plus a data quality log that can be loaded straight into Power BI.

Run:  python clean_meal_data.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)

log = []


def record(table, check, rows, action):
    log.append({"table": table, "check": check, "rows_affected": int(rows), "action": action})


# ----------------------------------------------------------------------------
# 1. Beneficiaries
# ----------------------------------------------------------------------------
ben = pd.read_csv(RAW / "raw_beneficiaries.csv")
n_raw = len(ben)

# 1a. Standardise text fields
ben["county"] = ben["county"].astype(str).str.strip().str.title()
ben["head_name"] = ben["head_name"].astype(str).str.strip().str.title()
changed = (pd.read_csv(RAW / "raw_beneficiaries.csv")["county"].astype(str) != ben["county"]).sum()
record("beneficiaries", "county spelling and case inconsistent", changed, "standardised to title case")

# 1b. Duplicate registrations: same head of household, same settlement, same household size.
# The earliest registration (lowest household id) is the one that is kept.
ben = ben.sort_values("household_id").reset_index(drop=True)
key = ["head_name", "settlement_cluster", "household_size"]
dup_mask = ben.duplicated(subset=key, keep="first")
ben["duplicate_flag"] = dup_mask
dups = ben[dup_mask][["household_id"] + key]
dups.to_csv(CLEAN / "flagged_duplicate_registrations.csv", index=False)
record("beneficiaries", "duplicate registration (name, settlement, household size)", dup_mask.sum(),
       "later registration removed, listed in flagged_duplicate_registrations.csv")
ben = ben[~dup_mask].drop(columns="duplicate_flag").copy()

# 1c. Missing subcounty: fill with the most common subcounty in the same settlement
miss = ben["subcounty"].isna()
mode_sub = ben.groupby("settlement_cluster")["subcounty"].agg(lambda s: s.mode().iloc[0])
ben.loc[miss, "subcounty"] = ben.loc[miss, "settlement_cluster"].map(mode_sub)
record("beneficiaries", "missing subcounty", miss.sum(), "filled from settlement cluster")

# 1d. Missing vulnerability score: fill with county median and keep a flag so analysts can exclude it
miss = ben["vulnerability_score"].isna()
ben["vulnerability_imputed"] = miss.astype(int)
med = ben.groupby("county")["vulnerability_score"].transform("median")
ben["vulnerability_score"] = ben["vulnerability_score"].fillna(med).round().astype(int)
record("beneficiaries", "missing vulnerability score", miss.sum(), "filled with county median, vulnerability_imputed = 1")

# 1e. Missing or impossible coordinates: Kenya sits roughly between lat -5 and 5.5, lon 33.5 and 42
bad = ben["latitude"].isna() | ben["longitude"].isna() | (ben["latitude"].abs() < 0.0001) | (ben["longitude"] < 33) | (ben["longitude"] > 42)
cent = ben[~bad].groupby("settlement_cluster")[["latitude", "longitude"]].median()
ben["coords_imputed"] = bad.astype(int)
for c in ["latitude", "longitude"]:
    ben.loc[bad, c] = ben.loc[bad, "settlement_cluster"].map(cent[c])
record("beneficiaries", "missing or invalid coordinates", bad.sum(), "set to settlement cluster median, coords_imputed = 1")

# 1f. Basic range checks
rng_issues = ((ben.household_size < 1) | (ben.household_size > 15) | (ben.vulnerability_score < 0) | (ben.vulnerability_score > 100)).sum()
record("beneficiaries", "household size or vulnerability score out of range", rng_issues, "none found" if rng_issues == 0 else "review")

# ----------------------------------------------------------------------------
# 2. Sites
# ----------------------------------------------------------------------------
sites = pd.read_csv(RAW / "raw_sites.csv")
sites["county"] = sites["county"].str.strip().str.title()
record("sites", "rows loaded", len(sites), "no changes needed")

# ----------------------------------------------------------------------------
# 3. Distributions and commodity batch validation
# ----------------------------------------------------------------------------
dist = pd.read_csv(RAW / "raw_distributions.csv")
n_dist_raw = len(dist)

# 3a. Exact repeats of the same site, date and commodity
rep = dist.duplicated(subset=["site_id", "dist_date", "commodity"], keep="first")
record("distributions", "repeated site, date and commodity line", rep.sum(), "removed")
dist = dist[~rep].copy()

# 3b. Unknown site ids go to a quarantine file instead of the model
unk = ~dist["site_id"].isin(sites["site_id"])
dist[unk].to_csv(CLEAN / "rejected_distributions_unknown_site.csv", index=False)
record("distributions", "site id not in site register", unk.sum(), "quarantined in rejected_distributions_unknown_site.csv")
dist = dist[~unk].copy()

# 3c. Missing dispatched quantity: use the received quantity (conservative) and flag it
miss = dist["qty_dispatched_mt"].isna()
dist["qty_flag"] = ""
dist.loc[miss, "qty_dispatched_mt"] = dist.loc[miss, "qty_received_mt"]
dist.loc[miss, "qty_flag"] = "dispatched_missing_filled_from_received"
record("distributions", "missing dispatched quantity", miss.sum(), "filled from received quantity and flagged")

# 3d. Received more than dispatched: treated as a transposition and swapped
swap = dist["qty_received_mt"] > dist["qty_dispatched_mt"] * 1.001
tmp = dist.loc[swap, "qty_dispatched_mt"].copy()
dist.loc[swap, "qty_dispatched_mt"] = dist.loc[swap, "qty_received_mt"]
dist.loc[swap, "qty_received_mt"] = tmp
dist.loc[swap, "qty_flag"] = "received_gt_dispatched_swapped"
record("distributions", "received quantity above dispatched quantity", swap.sum(), "values swapped and flagged for field confirmation")

# 3e. Zero, negative, or dispatched above 110 percent of plan
nonpos = (dist[["qty_planned_mt", "qty_dispatched_mt", "qty_received_mt"]] <= 0).any(axis=1)
over = dist["qty_dispatched_mt"] > dist["qty_planned_mt"] * 1.10
record("distributions", "zero or negative quantity", nonpos.sum(), "none found" if nonpos.sum() == 0 else "review")
record("distributions", "dispatched above 110 percent of plan", over.sum(), "none found" if over.sum() == 0 else "review")

# 3f. Batch reconciliation: at county and month level, received must not exceed dispatched
chk = dist.merge(sites[["site_id", "county"]], on="site_id")
chk["month"] = chk["dist_date"].str[:7]
g = chk.groupby(["county", "month"])[["qty_dispatched_mt", "qty_received_mt"]].sum()
record("distributions", "county month batches where received exceeds dispatched", (g.qty_received_mt > g.qty_dispatched_mt).sum(),
       "reconciled" if (g.qty_received_mt > g.qty_dispatched_mt).sum() == 0 else "review")

# ----------------------------------------------------------------------------
# 4. Ration receipts: keep only households that survived de duplication
# ----------------------------------------------------------------------------
rec = pd.read_csv(RAW / "raw_ration_receipts.csv")
orphan = ~rec["household_id"].isin(ben["household_id"])
record("ration_receipts", "receipt rows with no matching household", orphan.sum(), "removed" if orphan.sum() else "none found")
rec = rec[~orphan]

# ----------------------------------------------------------------------------
# 5. Write outputs
# ----------------------------------------------------------------------------
ben.to_csv(CLEAN / "beneficiaries.csv", index=False)
sites.to_csv(CLEAN / "sites.csv", index=False)
dist.to_csv(CLEAN / "distributions.csv", index=False)
rec.to_csv(CLEAN / "ration_receipts.csv", index=False)
pd.DataFrame(log).to_csv(CLEAN / "data_quality_log.csv", index=False)

print(f"Beneficiaries: {n_raw} raw rows to {len(ben)} clean rows")
print(f"Distributions: {n_dist_raw} raw rows to {len(dist)} clean rows")
print(pd.DataFrame(log).to_string(index=False))
