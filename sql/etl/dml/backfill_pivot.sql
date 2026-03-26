-- Phase 1: Dimension Pivot (Time-Bounded)
-- Table: silver.mv_varinst_pivoted
WITH target_procs AS (
    -- Only process variables for process instances that have task activity in the current window
    SELECT DISTINCT PROC_INST_ID_
    FROM bronze.bpm_act_hi_taskinst
    WHERE (START_TIME_ >= '{start_ts}' AND START_TIME_ <= '{end_ts}')
       OR (CLAIM_TIME_ >= '{start_ts}' AND CLAIM_TIME_ <= '{end_ts}')
       OR (END_TIME_ >= '{start_ts}' AND END_TIME_ <= '{end_ts}')
)
INSERT INTO silver.mv_varinst_pivoted
SELECT
    v.PROC_INST_ID_,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'region') AS varinst_region,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'plant') AS varinst_plant,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'factory') AS varinst_factory,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'lineName') AS varinst_lineName,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'moNumber') AS varinst_moNumber,
    argMaxIf(if(v.LONG_ = 1, 'true', 'false'), v.REV_, v.NAME_ = 'autoComplete') AS varinst_autoComplete,
    now() AS _refresh_time
FROM bronze.bpm_act_hi_varinst v
INNER JOIN target_procs t ON v.PROC_INST_ID_ = t.PROC_INST_ID_
WHERE v.NAME_ IN ('region', 'plant', 'factory', 'lineName', 'moNumber', 'autoComplete')

  AND v.CREATE_TIME_ >= parseDateTimeBestEffort('{start_ts}') - INTERVAL 180 DAY
  AND v.CREATE_TIME_ <= '{end_ts}'
GROUP BY v.PROC_INST_ID_



