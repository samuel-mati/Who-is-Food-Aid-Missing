-- 01_schema.sql
-- Relational model for the "Who Is Food Aid Missing?" project.
-- Written in SQLite syntax. It ports to MySQL or Azure SQL with small type changes
-- (TEXT to VARCHAR, REAL to DECIMAL or FLOAT).

DROP TABLE IF EXISTS tbl_Ration_Receipts;
DROP TABLE IF EXISTS tbl_Household_Coverage;
DROP TABLE IF EXISTS tbl_Distributions;
DROP TABLE IF EXISTS tbl_Beneficiaries;
DROP TABLE IF EXISTS tbl_Sites_GIS;

CREATE TABLE tbl_Sites_GIS (
    site_id             TEXT PRIMARY KEY,
    site_name           TEXT NOT NULL,
    county              TEXT NOT NULL,
    latitude            REAL NOT NULL CHECK (latitude BETWEEN -5 AND 5.5),
    longitude           REAL NOT NULL CHECK (longitude BETWEEN 33.5 AND 42),
    operational_status  TEXT NOT NULL CHECK (operational_status IN ('Active', 'Suspended')),
    max_radius_km       REAL NOT NULL
);

CREATE TABLE tbl_Beneficiaries (
    household_id           TEXT PRIMARY KEY,
    head_name              TEXT NOT NULL,
    county                 TEXT NOT NULL,
    subcounty              TEXT NOT NULL,
    settlement_cluster     TEXT NOT NULL,
    household_size         INTEGER NOT NULL,
    vulnerability_score    INTEGER NOT NULL CHECK (vulnerability_score BETWEEN 0 AND 100),
    target_rations         INTEGER NOT NULL,
    enrol_date             TEXT NOT NULL,
    latitude               REAL NOT NULL,
    longitude              REAL NOT NULL,
    vulnerability_imputed  INTEGER NOT NULL DEFAULT 0,
    coords_imputed         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE tbl_Distributions (
    dist_id             TEXT PRIMARY KEY,
    site_id             TEXT NOT NULL REFERENCES tbl_Sites_GIS(site_id),
    dist_date           TEXT NOT NULL,
    commodity           TEXT NOT NULL,
    qty_planned_mt      REAL NOT NULL,
    qty_dispatched_mt   REAL NOT NULL,
    qty_received_mt     REAL NOT NULL,
    qty_flag            TEXT
);

CREATE TABLE tbl_Ration_Receipts (
    household_id        TEXT NOT NULL REFERENCES tbl_Beneficiaries(household_id),
    ration_month        TEXT NOT NULL,
    rations_received    INTEGER NOT NULL CHECK (rations_received IN (0, 1)),
    PRIMARY KEY (household_id, ration_month)
);

-- Output of walk_less_analysis.py: nearest active site and distance band per household
CREATE TABLE tbl_Household_Coverage (
    household_id        TEXT PRIMARY KEY REFERENCES tbl_Beneficiaries(household_id),
    nearest_site_id     TEXT NOT NULL REFERENCES tbl_Sites_GIS(site_id),
    nearest_site_km     REAL NOT NULL,
    coverage_band       TEXT NOT NULL CHECK (coverage_band IN ('Within 5 km', '5 to 10 km', 'Over 10 km'))
);

CREATE INDEX ix_dist_site_date ON tbl_Distributions (site_id, dist_date);
CREATE INDEX ix_receipts_month ON tbl_Ration_Receipts (ration_month);
CREATE INDEX ix_ben_county ON tbl_Beneficiaries (county, settlement_cluster);
