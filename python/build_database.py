"""
build_database.py
Builds meal.db (SQLite) from the cleaned CSV files and runs the analysis queries.
Run order: clean_meal_data.py, walk_less_analysis.py, build_database.py
"""
from pathlib import Path
import re
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
DB = ROOT / "meal.db"

if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)
con.executescript((ROOT / "sql" / "01_schema.sql").read_text())


def load(table, df):
    df.to_sql(table, con, if_exists="append", index=False)


load("tbl_Sites_GIS", pd.read_csv(CLEAN / "sites.csv"))
load("tbl_Beneficiaries", pd.read_csv(CLEAN / "beneficiaries.csv"))
d = pd.read_csv(CLEAN / "distributions.csv")
d["qty_flag"] = d["qty_flag"].fillna("")
load("tbl_Distributions", d)
load("tbl_Ration_Receipts", pd.read_csv(CLEAN / "ration_receipts.csv"))
cov = pd.read_csv(CLEAN / "household_coverage.csv")[["household_id", "nearest_site_id", "nearest_site_km", "coverage_band"]]
load("tbl_Household_Coverage", cov)
con.commit()

# Run each query in 02_analysis_queries.sql and save the results for the dashboard
sql = (ROOT / "sql" / "02_analysis_queries.sql").read_text()
blocks = re.split(r"(?m)^-- (Q\d+)\.", sql)
out = ROOT / "data" / "clean" / "query_results"
out.mkdir(exist_ok=True)
for i in range(1, len(blocks), 2):
    name, body = blocks[i], blocks[i + 1]
    body = body.split("\n", 1)[1]
    df = pd.read_sql_query(body, con)
    df.to_csv(out / f"{name}.csv", index=False)
    print(name, df.shape)
con.close()
