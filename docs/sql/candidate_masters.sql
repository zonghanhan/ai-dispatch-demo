-- AI Dispatch Demo: list candidate masters (read-only)
-- Params:
--   :service_type_code  e.g. LX002 (from order.bizType)
--   :erp_code           exact match from order goods erpCode → erp_service_category.code
--   :city_name          e.g. 深圳市 (from order.city)
--   :limit              default 50

SELECT
    mu.master_id,
    mu.master_name,
    mu.nbs_id,
    mu.company,
    mu.master_type,
    est.name AS profession_type,
    msat.service_area_name AS service_city,
    msa.is_key_service_area,
    CAST(loc.lat AS DECIMAL(10, 6)) AS lat,
    CAST(loc.lon AS DECIMAL(10, 6)) AS lng,
    COALESCE(active.cnt, 0) AS active_orders,
    GREATEST(0.0, LEAST(1.0, 1.0 - COALESCE(active.cnt, 0) * 0.01)) AS free_ratio,
    GROUP_CONCAT(DISTINCT esc.code ORDER BY esc.code SEPARATOR ',') AS skill_codes,
    1 AS skill_match
FROM master_users mu
INNER JOIN master_service_type_category mstc
    ON mstc.master_id = mu.id AND mstc.deleted = 0
INNER JOIN erp_service_category esc
    ON esc.id = mstc.service_category_id AND esc.deleted = 0
INNER JOIN erp_service_type est
    ON est.code = mstc.service_type_id AND est.deleted = 0
    AND est.code = :service_type_code
INNER JOIN master_service_area msa
    ON msa.master_id = mu.id AND msa.deleted = 0
INNER JOIN master_service_area_tree msat
    ON msat.service_area_id = msa.service_city_id AND msat.deleted = 0
    AND msat.service_area_name = :city_name
LEFT JOIN (
    SELECT ma.user_id, mad.lat, mad.lon,
           ROW_NUMBER() OVER (PARTITION BY ma.user_id ORDER BY mad.clock_time DESC) AS rn
    FROM master_attendance ma
    JOIN master_attendance_detail mad
        ON mad.attendance_id = ma.id AND mad.deleted = 0
    WHERE ma.deleted = 0
      AND mad.lat IS NOT NULL AND mad.lat != ''
) loc ON loc.user_id = mu.id AND loc.rn = 1
LEFT JOIN (
    SELECT master_id, COUNT(*) AS cnt
    FROM order_order_master
    WHERE deleted = 0 AND master_status IN (1, 2, 3, 4)
    GROUP BY master_id
) active ON active.master_id = mu.id
WHERE mu.deleted = 0
  AND mu.status = 0
  AND mu.job_status IN (0, 1)
  AND mu.enter_status = 1
  AND esc.code = :erp_code
GROUP BY
    mu.master_id, mu.master_name, mu.nbs_id, mu.company, mu.master_type,
    est.name, msat.service_area_name, msa.is_key_service_area,
    loc.lat, loc.lon, active.cnt
LIMIT :limit;
