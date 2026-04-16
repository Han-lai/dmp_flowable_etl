-- Phase 3: Silver Fact Table (Time-Bounded)
-- Variables: {start_date}, {end_date}
INSERT INTO silver.mv_fact_task_vx
SELECT
    t.ID_ AS task_id,
    t.START_TIME_ AS task_start_time,

    t.CLAIM_TIME_ AS task_claim_time,
    t.END_TIME_ AS task_end_time,
    toDate(t.START_TIME_) AS task_start_date,        
    NULLIF(toDate(t.CLAIM_TIME_), toDate('1970-01-01')) AS task_claim_date,        
    NULLIF(toDate(t.END_TIME_), toDate('1970-01-01')) AS task_end_date,            
    toDate(COALESCE(t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_)) AS task_primary_date,
    toDate(COALESCE(t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_)) AS task_create_date,

    
    CASE 
        WHEN t.END_TIME_ IS NOT NULL THEN 'DONE'
        WHEN t.ASSIGNEE_ IS NOT NULL AND t.ASSIGNEE_ != '' THEN 'DOING'
        ELSE 'TODO'
    END AS task_status,
    
    CASE 
        -- 規則 1: 特定工單號 → V1
        WHEN substring(COALESCE(v_pivot.varinst_moNumber, ''), 1, 3) IN ('196','199','200','210','212','213')
        THEN 'V1'
        -- 規則 2-4: TASK_DEF_KEY_ 前綴匹配
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        -- 規則 5: 預設
        ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
    END AS vx_type,
    
    COALESCE(NULLIF(v_pivot.varinst_region, ''), mdm.region_code, plant_mdm.region_code, 'UNKNOWN') AS region,
    COALESCE(NULLIF(v_pivot.varinst_plant, ''), mdm.plant_code, 'UNKNOWN') AS plant,
    COALESCE(NULLIF(v_pivot.varinst_factory, ''), mdm.factory_code, 'UNKNOWN') AS factory,
    COALESCE(NULLIF(v_pivot.varinst_lineName, ''), mdm.line_name, 'UNKNOWN') AS line,
    
    CASE WHEN v_pivot.varinst_region != '' THEN 'VARINST' 
         WHEN mdm.region_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS region_source,
    CASE WHEN v_pivot.varinst_plant != '' THEN 'VARINST'
         WHEN mdm.plant_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS plant_source,
    CASE WHEN v_pivot.varinst_factory != '' THEN 'VARINST'
         WHEN mdm.factory_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS factory_source,
    CASE WHEN v_pivot.varinst_lineName != '' THEN 'VARINST'
         WHEN mdm.line_name IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS line_source,
    
    multiIf(tb.LONG_ = 1, 1, 
            (t.TASK_DEF_KEY_ LIKE 'E%') OR (t.TASK_DEF_KEY_ LIKE 'C%'), 1, 
            (COALESCE(v_pivot.varinst_moNumber, '') LIKE 'Q%') OR (COALESCE(v_pivot.varinst_moNumber, '') LIKE 'R%'), 1, 
            (t.NAME_ LIKE '%Notify%') OR (t.NAME_ LIKE '%Dummy%'), 1, 
            0) AS is_excluded,
    multiIf(tb.LONG_ = 1, 'bypass',
            t.TASK_DEF_KEY_ LIKE 'E%', 'system_node',
            t.TASK_DEF_KEY_ LIKE 'C%', 'system_node',
            COALESCE(v_pivot.varinst_moNumber, '') LIKE 'Q%', 'Q_order',
            COALESCE(v_pivot.varinst_moNumber, '') LIKE 'R%', 'R_order',
            t.NAME_ LIKE '%Notify%', 'notify_task',
            t.NAME_ LIKE '%Dummy%', 'dummy_task',
            '') AS exclude_reason,
    
    t.ASSIGNEE_ AS assignee_code,
    he.EmpName AS assignee_name,
    
    t.TASK_DEF_KEY_ AS task_definition_key,
    t.NAME_ AS task_name,
    v_pivot.varinst_moNumber AS mo_number,
    t.PROC_INST_ID_ AS proc_inst_id,
    now() AS _mview_update_time
FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN (
    -- Only load needed process instances into join RAM
    SELECT * FROM silver.mv_varinst_pivoted
    WHERE PROC_INST_ID_ IN (
        SELECT DISTINCT PROC_INST_ID_ FROM bronze.bpm_act_hi_taskinst
        WHERE (START_TIME_ >= '{start_ts}' AND START_TIME_ <= '{end_ts}')
           OR (CLAIM_TIME_ >= '{start_ts}' AND CLAIM_TIME_ <= '{end_ts}')
           OR (END_TIME_ >= '{start_ts}' AND END_TIME_ <= '{end_ts}')
    )
) AS v_pivot ON t.PROC_INST_ID_ = v_pivot.PROC_INST_ID_
LEFT JOIN silver.mv_dim_mfg_five_level AS mdm ON (v_pivot.varinst_lineName = mdm.line_name) AND (v_pivot.varinst_plant = mdm.plant_code)
LEFT JOIN (
    SELECT DISTINCT plant_code, region_code 
    FROM silver.mv_dim_mfg_five_level 
    WHERE plant_code != '' AND region_code IS NOT NULL
) AS plant_mdm ON COALESCE(NULLIF(v_pivot.varinst_plant, ''), mdm.plant_code, '') = plant_mdm.plant_code
LEFT JOIN bronze.common_hr_employee AS he ON t.ASSIGNEE_ = he.EmpCode
LEFT JOIN (
    -- Only load needed task variables into join RAM
    SELECT TASK_ID_, LONG_
    FROM bronze.bpm_act_hi_varinst
    WHERE NAME_ = 'autoComplete' AND TASK_ID_ IS NOT NULL AND TASK_ID_ != ''
      AND TASK_ID_ IN (
          SELECT DISTINCT ID_ FROM bronze.bpm_act_hi_taskinst
          WHERE (START_TIME_ >= toDateTime64('{start_ts}', 3) AND START_TIME_ <= toDateTime64('{end_ts}', 3))
             OR (CLAIM_TIME_ >= toDateTime64('{start_ts}', 3) AND CLAIM_TIME_ <= toDateTime64('{end_ts}', 3))
             OR (END_TIME_ >= toDateTime64('{start_ts}', 3) AND END_TIME_ <= toDateTime64('{end_ts}', 3))
      )
) AS tb ON t.ID_ = tb.TASK_ID_

WHERE (t.ID_ IS NOT NULL) AND (t.ID_ != '')
  AND (
      (t.START_TIME_ >= '{start_ts}' AND t.START_TIME_ <= '{end_ts}') OR
      (t.CLAIM_TIME_ >= '{start_ts}' AND t.CLAIM_TIME_ <= '{end_ts}') OR
      (t.END_TIME_ >= '{start_ts}' AND t.END_TIME_ <= '{end_ts}')
  )

