"""
build_erd.py
Draws the entity relationship diagram (docs/erd.png) for the SQLite model in sql/01_schema.sql.
Run:  python build_erd.py
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
STEEL, GOLD, BLUE, MUTE, ALT = "#1C2B3A", "#F4B400", "#05668D", "#566474", "#F3F5F8"
TABLES = {
    "tbl_Distributions": (0.2, [("dist_id", "PK"), ("site_id", "FK"), ("dist_date", ""), ("commodity", ""), ("qty_planned_mt", ""),
                            ("qty_dispatched_mt", ""), ("qty_received_mt", ""), ("qty_flag", "")]),
    "tbl_Sites_GIS": (2.75, [("site_id", "PK"), ("site_name", ""), ("county", ""), ("latitude", ""), ("longitude", ""),
                     ("operational_status", ""), ("max_radius_km", "")]),
    "tbl_Household_Coverage": (5.3, [("household_id", "PK FK"), ("nearest_site_id", "FK"), ("nearest_site_km", ""), ("coverage_band", "")]),
    "tbl_Beneficiaries": (7.85, [("household_id", "PK"), ("head_name", ""), ("county", ""), ("subcounty", ""), ("settlement_cluster", ""),
                             ("household_size", ""), ("vulnerability_score", ""), ("target_rations", ""), ("enrol_date", ""),
                             ("latitude", ""), ("longitude", ""), ("vulnerability_imputed", ""), ("coords_imputed", "")]),
    "tbl_Ration_Receipts": (10.4, [("household_id", "PK FK"), ("ration_month", "PK"), ("rations_received", "")]),
}
W, ROWH, HEAD, TOP = 1.95, 0.27, 0.32, 4.7
fig, ax = plt.subplots(figsize=(15.5, 5.4), dpi=200)
ax.set_xlim(0, 12.55); ax.set_ylim(0, 5.9); ax.axis("off")
ax.text(0.2, 5.55, "Entity relationship diagram", fontsize=21, fontweight="bold", color=STEEL, family="serif", va="center")
ax.text(0.2, 5.12, f"Who Is Food Aid Missing? SQLite model (ports to MySQL or Azure SQL)",
        fontsize=10.5, color=MUTE, family="serif", va="center")
ax.add_patch(Rectangle((0.2, 4.95), 1.6, 0.04, color=GOLD))
pos = {}
for name, (x, cols) in TABLES.items():
    h = HEAD + ROWH * len(cols)
    ax.add_patch(Rectangle((x, TOP - h), W, h, fill=False, ec=STEEL, lw=1.4))
    ax.add_patch(Rectangle((x, TOP - HEAD), W, HEAD, color=STEEL))
    ax.add_patch(Rectangle((x, TOP - HEAD - 0.04), W, 0.04, color=GOLD))
    ax.text(x + 0.09, TOP - HEAD / 2, name, color="white", fontsize=10.5, fontweight="bold", family="serif", va="center")
    for i, (c, k) in enumerate(cols):
        y = TOP - HEAD - ROWH * (i + 1)
        if i % 2: ax.add_patch(Rectangle((x + 0.01, y), W - 0.02, ROWH, color=ALT, lw=0))
        ax.text(x + 0.09, y + ROWH / 2, c, fontsize=8.6, color=STEEL, family="serif", va="center")
        ax.text(x + W - 0.08, y + ROWH / 2, k, fontsize=7.6, color=BLUE, fontweight="bold", ha="right", va="center")
        pos[(name, c)] = (x, y + ROWH / 2)
def link(a, b, la, lb):
    (xa, ya), (xb, yb) = pos[a], pos[b]
    if xa < xb: x1, x2, s1, s2 = xa + W, xb, 1, -1
    else: x1, x2, s1, s2 = xa, xb + W, -1, 1
    ax.plot([x1, x2], [ya, yb], color=BLUE, lw=1.6)
    ax.text(x1 + s1 * 0.16, ya + 0.12, la, fontsize=9, fontweight="bold", color=STEEL, family="serif", ha="center")
    ax.text(x2 + s2 * 0.16, yb + 0.12, lb, fontsize=9, fontweight="bold", color=STEEL, family="serif", ha="center")
link(("tbl_Distributions", "site_id"), ("tbl_Sites_GIS", "site_id"), "N", "1")
link(("tbl_Sites_GIS", "site_id"), ("tbl_Household_Coverage", "nearest_site_id"), "1", "N")
link(("tbl_Household_Coverage", "household_id"), ("tbl_Beneficiaries", "household_id"), "1", "1")
link(("tbl_Beneficiaries", "household_id"), ("tbl_Ration_Receipts", "household_id"), "1", "N")
ax.text(0.2, 0.15, "PK = primary key, FK = foreign key, 1 and N mark the relationship side.   Prepared by Samuel Mati",
        fontsize=8.6, color=MUTE, family="serif")
fig.savefig(ROOT / "docs" / "erd.png", bbox_inches="tight", facecolor="white")
