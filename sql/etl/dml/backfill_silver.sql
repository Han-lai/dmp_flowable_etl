-- Phase 4: Silver Fact Table (Time-Bounded V4.3 Super Silver)
-- 目標表: silver.mv_fact_task_vx
-- 目的：將流程任務 (Task) 的基礎資訊、時效、業務變數與週期狀態進行大統一聚合，作為 KPI 與明細報表的唯一來源
-- Variables: {start_ts}, {end_ts} - 增量/分段回填的時間區間

INSERT INTO silver.mv_fact_task_vx
SELECT
    -- [A] 識別資訊：追蹤任務與流程的唯一 ID
    t.ID_ AS task_id,                          -- 任務執行實例 ID (Primary Key)
    t.PROC_INST_ID_ AS proc_inst_id,           -- 流程實例 ID (關聯變數與流程狀態的主鍵)
    pi.BUSINESS_STATUS_ AS l4_process_id,      -- L4 流程編號 (從流程實例獲取，用於區分業務流程類型)
    pd.NAME_ AS l4_process_name,               -- 流程名稱 (從流程定義表獲取，如：產線報工、物料申請)
    t.TASK_DEF_KEY_ AS task_definition_key,    -- 任務定義 Key (如：V1_Task_01，用於判斷階段與邏輯分類)
    t.NAME_ AS task_name,                      -- 任務顯示名稱 (如：組裝、測試、包裝)
    
    -- [B] 時間軸與時效指標 (分鐘)：記錄任務生命週期與效率
    t.START_TIME_ AS task_start_time,          -- 任務開始時間 (開單日)
    NULLIF(t.CLAIM_TIME_, toDateTime('1970-01-01')) AS task_claim_time, -- 簽收時間 (人員點擊開始處理的時間，排除預設值)
    NULLIF(t.END_TIME_, toDateTime('1970-01-01')) AS task_end_time,     -- 完成時間 (人員點擊完成的時間)
    
    toDate(t.START_TIME_) AS task_start_date,          -- 開始日期 (Date 格式，用於日常分區查詢)
    NULLIF(toDate(t.CLAIM_TIME_), toDate('1970-01-01')) AS task_claim_date, -- 簽收日期
    NULLIF(toDate(t.END_TIME_), toDate('1970-01-01')) AS task_end_date,     -- 完成日期
    toDate(t.START_TIME_) AS task_primary_date,        -- 主日期 (統一以開單日作為 KPI 錨定日期，確保數據不跨日偏移)
    toDate(t.START_TIME_) AS task_create_date,         -- 建立日期
    
    -- 計算持續時間 (Duration)：從開始到完成的總時長
    CASE WHEN t.END_TIME_ IS NOT NULL AND toDate(t.END_TIME_) != toDate('1970-01-01') 
         THEN dateDiff('second', t.START_TIME_, t.END_TIME_) / 60.0 ELSE NULL END AS duration_min,
    
    -- 計算處理時間 (Processing)：從簽收至完成的實際作業時長，反映人員作業效率
    CASE WHEN t.END_TIME_ IS NOT NULL AND toDate(t.END_TIME_) != toDate('1970-01-01') 
          AND t.CLAIM_TIME_ IS NOT NULL AND toDate(t.CLAIM_TIME_) != toDate('1970-01-01')
         THEN dateDiff('second', t.CLAIM_TIME_, t.END_TIME_) / 60.0 ELSE NULL END AS processing_time_min,
         
    v_pivot.varinst_time AS ui_time_field,     -- 介面自定義時間欄位 (從業務變數提取)
    
    -- [C] 狀態與結算標籤 (Cohort)：依據不同週期粒度判定任務「當時」的結算狀態
    -- Live Status: 任務目前的真實物理狀態 (TODO/DOING/DONE)
    CASE 
        WHEN t.END_TIME_ IS NOT NULL AND toDate(t.END_TIME_) != toDate('1970-01-01') THEN 'DONE'
        WHEN t.ASSIGNEE_ IS NOT NULL AND t.ASSIGNEE_ != '' THEN 'DOING'
        ELSE 'TODO'
    END AS task_status,
    
    -- 日結算：任務是否在「開單日當天」完工，用於日報表結算
    CASE WHEN t.END_TIME_ IS NOT NULL AND toDate(t.END_TIME_) = toDate(t.START_TIME_) THEN 'DONE'
         WHEN t.CLAIM_TIME_ IS NOT NULL AND toDate(t.CLAIM_TIME_) = toDate(t.START_TIME_) THEN 'DOING'
         ELSE 'TODO' END AS status_daily,
         
    -- 週結算：任務是否在「開單當週」結束前完工，用於週報表結算 (確保跨日任務在週報不重複計數)
    CASE WHEN t.END_TIME_ IS NOT NULL AND toDate(t.END_TIME_) <= (toStartOfWeek(toDate(t.START_TIME_), 3) + INTERVAL 6 DAY) THEN 'DONE'
         WHEN t.CLAIM_TIME_ IS NOT NULL AND toDate(t.CLAIM_TIME_) <= (toStartOfWeek(toDate(t.START_TIME_), 3) + INTERVAL 6 DAY) THEN 'DOING'
         ELSE 'TODO' END AS status_weekly,
         
    -- 月結算：任務是否在「開單當月」結束前完工，用於月報表結算
    CASE WHEN t.END_TIME_ IS NOT NULL AND toDate(t.END_TIME_) <= toLastDayOfMonth(toDate(t.START_TIME_)) THEN 'DONE'
         WHEN t.CLAIM_TIME_ IS NOT NULL AND toDate(t.CLAIM_TIME_) <= toLastDayOfMonth(toDate(t.START_TIME_)) THEN 'DOING'
         ELSE 'TODO' END AS status_monthly,

    -- [D] 製造五階維度：定義業務分類 (V1/V2/V3)
    CASE 
        -- 優先判定特殊工單前綴，歸類為 V1
        WHEN substring(COALESCE(v_pivot.varinst_moNumber, ''), 1, 3) IN ('196','199','200','210','212','213') THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- 區域/廠別/工廠/線別維度：優先採用業務變數 (Manual Input)，若無則採用 MDM 主檔推導
    -- region 取值順序：varinst → 精確 MDM (line+plant) → 備援 MDM (plant only) → '' (空字串)
    -- 備援 MDM 適用情境：① lineName 為空 ② lineName 有值但不在 MDM（如 NEP1 等未收錄線別）
    -- 注意：ClickHouse LEFT JOIN 失敗時 String 欄位回傳 '' 而非 NULL，必須用 NULLIF 轉換後 COALESCE 才能正確跳過
    -- 無法取得或回推時保留空字串，不填 UNKNOWN
    COALESCE(
        NULLIF(v_pivot.varinst_region, ''),
        NULLIF(mdm.region_code, ''),
        NULLIF(mdm_plant.region_code, ''),
        ''
    ) AS region,
    COALESCE(NULLIF(v_pivot.varinst_plant, ''), NULLIF(mdm.plant_code, ''), '') AS plant,
    COALESCE(NULLIF(v_pivot.varinst_factory, ''), NULLIF(mdm.factory_code, ''), '') AS factory,
    COALESCE(NULLIF(v_pivot.varinst_lineName, ''), NULLIF(mdm.line_name, ''), '') AS line,
    
    -- [E] 業務變數 (11 欄)：從流程變數中轉置提取的具體業務內容
    COALESCE(v_pivot.varinst_moNumber, '') AS mo_number,             -- 工單號碼
    COALESCE(v_pivot.varinst_modelName, '') AS model_name,           -- 機種名稱
    COALESCE(v_pivot.varinst_deliveryArea, '') AS delivery_area,     -- 交付區域
    COALESCE(v_pivot.varinst_scheduleNumber, '') AS schedule_number, -- 排程編號
    COALESCE(v_pivot.varinst_sapPlant, '') AS sap_plant,             -- SAP 廠別
    COALESCE(v_pivot.varinst_sapProductGroup, '') AS sap_product_group, -- SAP 產品組
    COALESCE(v_pivot.varinst_pallet, '') AS pallet,                 -- 棧板編號
    COALESCE(v_pivot.varinst_transferNo, '') AS transfer_no,         -- 轉單編號
    COALESCE(v_pivot.varinst_qBlockEventId, '') AS qblock_event_id,   -- Q-Block 事件 ID
    COALESCE(v_pivot.varinst_defectSn, '') AS defect_sn,             -- 不良品 SN
    
    -- is_excluded: 任務排除邏輯，確保 KPI 只統計具備商業意義的生產任務
    -- 包含：自動完成、系統帳號、系統節點、Q/R 測試單、通知/虛擬任務
    multiIf(tb.LONG_ = 1, 1,
            he.EmpName = 'SYSTEM', 1,
            (t.TASK_DEF_KEY_ LIKE 'E%') OR (t.TASK_DEF_KEY_ LIKE 'C%'), 1, 
            (COALESCE(v_pivot.varinst_moNumber, '') LIKE 'Q%') OR (COALESCE(v_pivot.varinst_moNumber, '') LIKE 'R%'), 1, 
            (t.NAME_ LIKE '%Notify%') OR (t.NAME_ LIKE '%Dummy%'), 1, 
            0) AS is_excluded,
    -- 排除原因描述：用於後續稽核
    multiIf(tb.LONG_ = 1, 'bypass',
            he.EmpName = 'SYSTEM', 'system_bypass',
            t.TASK_DEF_KEY_ LIKE 'E%', 'system_node',
            t.TASK_DEF_KEY_ LIKE 'C%', 'system_node',
            COALESCE(v_pivot.varinst_moNumber, '') LIKE 'Q%', 'Q_order',
            COALESCE(v_pivot.varinst_moNumber, '') LIKE 'R%', 'R_order',
            t.NAME_ LIKE '%Notify%', 'notify_task',
            t.NAME_ LIKE '%Dummy%', 'dummy_task',
            '') AS exclude_reason,
            
    t.ASSIGNEE_ AS assignee_code,              -- 處理人代碼
    he.EmpName AS assignee_name,               -- 處理人姓名 (關聯 HR 主檔)
    
    now() AS _mview_update_time                -- 資料寫入/更新時間戳記

FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN bronze.bpm_act_hi_procinst AS pi ON t.PROC_INST_ID_ = pi.ID_ -- 獲取流程級別狀態 (BUSINESS_STATUS_ 為 L4 編號)
LEFT JOIN bronze.bpm_act_re_procdef AS pd ON t.PROC_DEF_ID_ = pd.ID_   -- 獲取流程定義名稱
LEFT JOIN (
    -- [關鍵效能與正確性優化]：加載變數攤平表
    -- 使用 argMax 確保同一個 PROC_INST_ID_ 僅取出最新版本的變數，防止 Join 產生重複數據 (Data Multiplication)
    SELECT 
        PROC_INST_ID_,
        argMax(varinst_region, _refresh_time) as varinst_region,
        argMax(varinst_plant, _refresh_time) as varinst_plant,
        argMax(varinst_factory, _refresh_time) as varinst_factory,
        argMax(varinst_lineName, _refresh_time) as varinst_lineName,
        argMax(varinst_moNumber, _refresh_time) as varinst_moNumber,
        argMax(varinst_modelName, _refresh_time) as varinst_modelName,
        argMax(varinst_deliveryArea, _refresh_time) as varinst_deliveryArea,
        argMax(varinst_scheduleNumber, _refresh_time) as varinst_scheduleNumber,
        argMax(varinst_sapPlant, _refresh_time) as varinst_sapPlant,
        argMax(varinst_sapProductGroup, _refresh_time) as varinst_sapProductGroup,
        argMax(varinst_pallet, _refresh_time) as varinst_pallet,
        argMax(varinst_transferNo, _refresh_time) as varinst_transferNo,
        argMax(varinst_qBlockEventId, _refresh_time) as varinst_qBlockEventId,
        argMax(varinst_defectSn, _refresh_time) as varinst_defectSn,
        argMax(varinst_time, _refresh_time) as varinst_time,
        argMax(varinst_autoComplete, _refresh_time) as varinst_autoComplete
    FROM silver.mv_varinst_pivoted
    WHERE PROC_INST_ID_ IN (
        -- 子查詢限制：僅處理當前時間視窗內的流程，大幅降低 Scan 量與記憶體負擔
        SELECT DISTINCT PROC_INST_ID_ FROM bronze.bpm_act_hi_taskinst
        WHERE (START_TIME_ >= '{start_ts}' AND START_TIME_ <= '{end_ts}')
           OR (CLAIM_TIME_ >= '{start_ts}' AND CLAIM_TIME_ <= '{end_ts}')
           OR (END_TIME_ >= '{start_ts}' AND END_TIME_ <= '{end_ts}')
    )
    GROUP BY PROC_INST_ID_
) AS v_pivot ON t.PROC_INST_ID_ = v_pivot.PROC_INST_ID_
LEFT JOIN silver.mv_dim_mfg_five_level AS mdm ON (v_pivot.varinst_lineName = mdm.line_name) AND (v_pivot.varinst_plant = mdm.plant_code) -- 精確配對：line + plant 都有時使用
LEFT JOIN (
    -- 備援 MDM：plant → region 對照表（ON 只用 join key，避免 ClickHouse 25.8 analyzer 誤處理複合條件）
    -- 使用條件 IF(lineName IS NULL, ...) 在 SELECT 層判斷是否採用此備援結果
    SELECT plant_code, region_code
    FROM silver.mv_dim_mfg_five_level
    WHERE plant_code != '' AND region_code != ''
    ORDER BY plant_code, region_code
    LIMIT 1 BY plant_code
) AS mdm_plant ON v_pivot.varinst_plant = mdm_plant.plant_code
LEFT JOIN bronze.common_hr_employee AS he ON t.ASSIGNEE_ = he.EmpCode -- 關聯人員主檔
LEFT JOIN (
    -- [排除邏輯子查詢]：獲取 autoComplete 業務變數 (1=自動跳過)
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
      -- 嚴格的時間視窗過濾，確保資料回填的精確性與增量效率，支援斷點續傳
      (t.START_TIME_ >= '{start_ts}' AND t.START_TIME_ <= '{end_ts}') OR
      (t.CLAIM_TIME_ >= '{start_ts}' AND t.CLAIM_TIME_ <= '{end_ts}') OR
      (t.END_TIME_ >= '{start_ts}' AND t.END_TIME_ <= '{end_ts}')
  )
SETTINGS allow_experimental_analyzer = 0
