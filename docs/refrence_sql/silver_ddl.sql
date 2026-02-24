CREATE MATERIALIZED VIEW silver.mv_fact_task_vx
(
    `task_id` String,
    `task_start_date` Date,
    `task_claim_date` Nullable(Date),
    `task_end_date` Nullable(Date),
    `task_primary_date` Date,
    `task_create_date` Date,
    `task_status` String,
    `vx_type` String,
    `region` String,
    `plant` String,
    `factory` String,
    `line` String,
    `region_source` String,
    `plant_source` String,
    `factory_source` String,
    `line_source` String,
    `is_excluded` UInt8,
    `exclude_reason` String,
    `assignee_code` Nullable(String),
    `assignee_name` Nullable(String),
    `task_definition_key` Nullable(String),
    `task_name` Nullable(String),
    `mo_number` Nullable(String),
    `proc_inst_id` Nullable(String),
    `_mview_update_time` DateTime64(3)
)
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY task_id
TTL task_primary_date + toIntervalYear(1)
SETTINGS allow_nullable_key = 1, index_granularity = 8192
AS SELECT
    t.ID_ AS task_id,
    toDate(t.START_TIME_) AS task_start_date,
    toDate(t.CLAIM_TIME_) AS task_claim_date,
    toDate(t.END_TIME_) AS task_end_date,
    toDate(coalesce(t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_)) AS task_primary_date,
    toDate(coalesce(t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_)) AS task_create_date,
    multiIf(t.END_TIME_ IS NOT NULL, 'DONE', (t.ASSIGNEE_ IS NOT NULL) AND (t.ASSIGNEE_ != ''), 'DOING', 'TODO') AS task_status,
    multiIf(t.TASK_DEF_KEY_ LIKE 'V1%', 'V1', t.TASK_DEF_KEY_ LIKE 'V2%', 'V2', t.TASK_DEF_KEY_ LIKE 'V3%', 'V3', coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE '315%', 'V1', (coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE '196%') OR (coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE '199%') OR (coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE '200%') OR (coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE '210%') OR (coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE '212%') OR (coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE '213%'), 'V1', coalesce(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')) AS vx_type,
    coalesce(nullIf(mv_varinst_pivoted.varinst_region, ''), mdm.region_code, 'UNKNOWN') AS region,
    coalesce(nullIf(mv_varinst_pivoted.varinst_plant, ''), mdm.plant_code, 'UNKNOWN') AS plant,
    coalesce(nullIf(mv_varinst_pivoted.varinst_factory, ''), mdm.factory_code, 'UNKNOWN') AS factory,
    coalesce(nullIf(mv_varinst_pivoted.varinst_lineName, ''), mdm.line_name, 'UNKNOWN') AS line,
    multiIf(mv_varinst_pivoted.varinst_region != '', 'VARINST', mdm.region_code IS NOT NULL, 'MDM', 'MISSING') AS region_source,
    multiIf(mv_varinst_pivoted.varinst_plant != '', 'VARINST', mdm.plant_code IS NOT NULL, 'MDM', 'MISSING') AS plant_source,
    multiIf(mv_varinst_pivoted.varinst_factory != '', 'VARINST', mdm.factory_code IS NOT NULL, 'MDM', 'MISSING') AS factory_source,
    multiIf(mv_varinst_pivoted.varinst_lineName != '', 'VARINST', mdm.line_name IS NOT NULL, 'MDM', 'MISSING') AS line_source,
    multiIf(tb.LONG_ = 1, 1, (t.TASK_DEF_KEY_ LIKE 'E%') OR (t.TASK_DEF_KEY_ LIKE 'C%'), 1, (coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE 'Q%') OR (coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE 'R%'), 1, (t.NAME_ LIKE '%Notify%') OR (t.NAME_ LIKE '%Dummy%'), 1, 0) AS is_excluded,
    multiIf(tb.LONG_ = 1, 'bypass', t.TASK_DEF_KEY_ LIKE 'E%', 'system_node', t.TASK_DEF_KEY_ LIKE 'C%', 'system_node', coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE 'Q%', 'Q_order', coalesce(mv_varinst_pivoted.varinst_moNumber, '') LIKE 'R%', 'R_order', t.NAME_ LIKE '%Notify%', 'notify_task', t.NAME_ LIKE '%Dummy%', 'dummy_task', '') AS exclude_reason,
    t.ASSIGNEE_ AS assignee_code,
    he.EmpName AS assignee_name,
    t.TASK_DEF_KEY_ AS task_definition_key,
    t.NAME_ AS task_name,
    mv_varinst_pivoted.varinst_moNumber AS mo_number,
    t.PROC_INST_ID_ AS proc_inst_id,
    now64(3) AS _mview_update_time
FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN silver.mv_varinst_pivoted ON t.PROC_INST_ID_ = mv_varinst_pivoted.PROC_INST_ID_
LEFT JOIN silver.mv_dim_mfg_five_level AS mdm ON mv_varinst_pivoted.varinst_lineName = mdm.line_name
LEFT JOIN bronze.common_hr_employee AS he ON t.ASSIGNEE_ = he.EmpCode
LEFT JOIN bronze.bpm_act_hi_varinst AS tb ON (t.ID_ = tb.TASK_ID_) AND (tb.NAME_ = 'autoComplete')
WHERE (t.ID_ IS NOT NULL) AND (t.ID_ != '')