-- 02_analysis_queries.sql
-- Analysis queries. Every query runs as is on the SQLite database built by build_database.py.

-- Q1. Monthly commodity completion rate per county, with month on month change (LAG window function)
WITH monthly AS (
    SELECT s.county,
           strftime('%Y-%m', d.dist_date)  AS month,
           SUM(d.qty_planned_mt)           AS planned_mt,
           SUM(d.qty_dispatched_mt)        AS dispatched_mt,
           SUM(d.qty_received_mt)          AS received_mt
    FROM tbl_Distributions d
    JOIN tbl_Sites_GIS s ON s.site_id = d.site_id
    GROUP BY s.county, strftime('%Y-%m', d.dist_date)
)
SELECT county,
       month,
       ROUND(planned_mt, 2)                                   AS planned_mt,
       ROUND(received_mt, 2)                                  AS received_mt,
       ROUND(received_mt - planned_mt, 2)                     AS variance_mt,
       ROUND(100.0 * received_mt / planned_mt, 1)             AS completion_rate_pct,
       ROUND(100.0 * received_mt / planned_mt
             - LAG(100.0 * received_mt / planned_mt) OVER (PARTITION BY county ORDER BY month), 1) AS change_vs_prior_month_pts
FROM monthly
ORDER BY county, month;

-- Q2. Planned versus actual by county and commodity, ranked by shortfall within each county
WITH base AS (
    SELECT s.county, d.commodity,
           SUM(d.qty_planned_mt)  AS planned_mt,
           SUM(d.qty_received_mt) AS received_mt
    FROM tbl_Distributions d
    JOIN tbl_Sites_GIS s ON s.site_id = d.site_id
    GROUP BY s.county, d.commodity
)
SELECT county, commodity,
       ROUND(planned_mt, 1)                        AS planned_mt,
       ROUND(received_mt, 1)                       AS received_mt,
       ROUND(planned_mt - received_mt, 1)          AS shortfall_mt,
       ROUND(100.0 * received_mt / planned_mt, 1)  AS completion_rate_pct,
       RANK() OVER (PARTITION BY county ORDER BY (planned_mt - received_mt) DESC) AS shortfall_rank
FROM base
ORDER BY county, shortfall_rank;

-- Q3. Beneficiary reach by month against target, with a running total (SUM window function)
WITH reach AS (
    SELECT ration_month,
           SUM(rations_received)                        AS households_reached,
           COUNT(*)                                     AS households_targeted
    FROM tbl_Ration_Receipts
    GROUP BY ration_month
)
SELECT ration_month,
       households_reached,
       households_targeted,
       ROUND(100.0 * households_reached / households_targeted, 1)                      AS reach_rate_pct,
       SUM(households_reached) OVER (ORDER BY ration_month)                            AS cumulative_rations_delivered,
       SUM(households_targeted) OVER (ORDER BY ration_month)                           AS cumulative_rations_target
FROM reach
ORDER BY ration_month;

-- Q4. Reach rate by distance band: does distance explain missed rations?
SELECT c.coverage_band,
       COUNT(DISTINCT c.household_id)                         AS households,
       ROUND(100.0 * SUM(r.rations_received) / COUNT(*), 1)   AS reach_rate_pct
FROM tbl_Household_Coverage c
JOIN tbl_Ration_Receipts r ON r.household_id = c.household_id
GROUP BY c.coverage_band
ORDER BY CASE c.coverage_band WHEN 'Within 5 km' THEN 1 WHEN '5 to 10 km' THEN 2 ELSE 3 END;

-- Q5. Access to distribution sites by county
SELECT b.county,
       COUNT(*)                                                                          AS households,
       ROUND(AVG(c.nearest_site_km), 1)                                                  AS avg_walk_km,
       ROUND(100.0 * SUM(c.coverage_band = 'Within 5 km') / COUNT(*), 1)                 AS pct_within_5km,
       ROUND(100.0 * SUM(c.coverage_band = 'Over 10 km') / COUNT(*), 1)                  AS pct_over_10km
FROM tbl_Beneficiaries b
JOIN tbl_Household_Coverage c ON c.household_id = b.household_id
GROUP BY b.county
ORDER BY pct_within_5km;

-- Q6. Site league table: completion rate and households served, ranked with RANK()
WITH served AS (
    SELECT nearest_site_id AS site_id, COUNT(*) AS households_served
    FROM tbl_Household_Coverage
    GROUP BY nearest_site_id
),
perf AS (
    SELECT site_id,
           SUM(qty_received_mt) / SUM(qty_planned_mt) * 100 AS completion_rate_pct
    FROM tbl_Distributions
    GROUP BY site_id
)
SELECT s.site_name, s.county, s.operational_status,
       COALESCE(v.households_served, 0)          AS households_served,
       ROUND(p.completion_rate_pct, 1)           AS completion_rate_pct,
       CASE WHEN p.completion_rate_pct IS NULL THEN NULL
            ELSE RANK() OVER (PARTITION BY (p.completion_rate_pct IS NULL) ORDER BY p.completion_rate_pct ASC)
       END AS worst_first_rank
FROM tbl_Sites_GIS s
LEFT JOIN served v ON v.site_id = s.site_id
LEFT JOIN perf p ON p.site_id = s.site_id
ORDER BY worst_first_rank IS NULL, worst_first_rank;

-- Q7. Months where a county fell more than 10 points below its own average completion rate
WITH monthly AS (
    SELECT s.county, strftime('%Y-%m', d.dist_date) AS month,
           100.0 * SUM(d.qty_received_mt) / SUM(d.qty_planned_mt) AS completion_rate_pct
    FROM tbl_Distributions d
    JOIN tbl_Sites_GIS s ON s.site_id = d.site_id
    GROUP BY s.county, strftime('%Y-%m', d.dist_date)
),
scored AS (
    SELECT county, month, completion_rate_pct,
           AVG(completion_rate_pct) OVER (PARTITION BY county) AS county_avg
    FROM monthly
)
SELECT county, month, ROUND(completion_rate_pct, 1) AS completion_rate_pct,
       ROUND(county_avg, 1) AS county_avg_pct
FROM scored
WHERE completion_rate_pct < county_avg - 10
ORDER BY county, month;
