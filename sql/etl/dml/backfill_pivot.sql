-- Phase 1: Dimension Pivot
-- Table: silver.mv_varinst_pivoted (PROC_INST_ID_, varinst_region, varinst_plant, varinst_factory, varinst_lineName, varinst_moNumber, varinst_autoComplete, _refresh_time)
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
GROUP BY PROC_INST_ID_
