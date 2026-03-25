-- Phase 1: Dimension Pivot (Time-Bounded)
-- Table: silver.mv_varinst_pivoted
INSERT INTO silver.mv_varinst_pivoted
SELECT
    PROC_INST_ID_,
    argMaxIf(TEXT_, REV_, NAME_ = 'region') AS varinst_region,
    argMaxIf(TEXT_, REV_, NAME_ = 'plant') AS varinst_plant,
    argMaxIf(TEXT_, REV_, NAME_ = 'factory') AS varinst_factory,
    argMaxIf(TEXT_, REV_, NAME_ = 'lineName') AS varinst_lineName,
    argMaxIf(TEXT_, REV_, NAME_ = 'moNumber') AS varinst_moNumber,
    argMaxIf(if(LONG_ = 1, 'true', 'false'), REV_, NAME_ = 'autoComplete') AS varinst_autoComplete,
    now() AS _refresh_time
FROM bronze.bpm_act_hi_varinst
WHERE PROC_INST_ID_ IS NOT NULL AND PROC_INST_ID_ != ''
  AND NAME_ IN ('region', 'plant', 'factory', 'lineName', 'moNumber', 'autoComplete')
  AND toDate(CREATE_TIME_) >= toDate('{start_date}') - INTERVAL 180 DAY
  AND toDate(CREATE_TIME_) <= toDate('{end_date}')
GROUP BY PROC_INST_ID_
