-- ==========================================
-- DML: UI Detail 專用明細寬表洗刷邏輯
-- 目的: 將 silver.mv_fact_task_vx 與擴充的 9 個變數、流程名稱組裝
-- 變數: {start_ts}, {end_ts}
-- ==========================================

INSERT INTO silver.mv_fact_ui_task_details
SELECT 
    -- [A] 任務基礎識別
    f.task_id,
    f.proc_inst_id,
    f.task_definition_key,
    f.task_name,
    COALESCE(p.NAME_, '') AS l4_process_name,
    
    -- [B] 業務客製化變數 (結合原本的與新增的)
    f.mo_number,
    COALESCE(v.ui_scheduleNumber, '') AS schedule_number,
    COALESCE(v.ui_sapPlant, '') AS sap_plant,
    COALESCE(v.ui_sapProductGroup, '') AS sap_product_group,
    COALESCE(v.ui_pallet, '') AS pallet,
    COALESCE(v.ui_transferNo, '') AS transfer_no,
    COALESCE(v.ui_qBlockEventId, '') AS qblock_event_id,
    COALESCE(v.ui_defectSn, '') AS defect_sn,
    COALESCE(v.ui_modelName, '') AS model_name,
    COALESCE(v.ui_deliveryArea, '') AS delivery_area,
    
    -- [C] 製造五階與分類 (直接繼承已計算好的結果)
    f.vx_type,
    f.region,
    f.plant,
    f.factory,
    f.line,
    
    -- [D] 時間軸 (直接繼承)
    f.task_start_time,
    f.task_claim_time,
    f.task_end_time,
    
    -- [E] 執行者 (直接繼承)
    f.assignee_code,
    f.assignee_name,
    
    -- [F] 狀態與稽核 (直接繼承 V4 Cohort 邏輯)
    f.task_status,
    f.is_excluded,
    f.exclude_reason,
    
    now() AS _mview_update_time
FROM silver.mv_fact_task_vx AS f
-- 關聯 1: 取出擴充的流程變數
LEFT JOIN silver.mv_ui_varinst_pivoted AS v ON f.proc_inst_id = v.PROC_INST_ID_
-- 關聯 2: 取出流程的完整中文/英文定義名稱
LEFT JOIN bronze.bpm_act_re_procdef AS p ON f.task_definition_key = p.KEY_
WHERE f.task_start_time >= toDate('{start_ts}')
  AND f.task_start_time <= toDate('{end_ts}');
