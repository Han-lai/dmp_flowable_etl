# DMP Flowable 前端明細表欄位對照指南 (UI Detail Fields Mapping)

**文件定位**: 本文件用於對照「業務/前端畫面需求明細欄位」與「底層資料庫 (`silver.mv_fact_ui_task_details`) 實體欄位」的映射關係。此表為專門獨立供應給前端的 31 欄終極明細寬表。

---

## 🟢 1. 完全對應 (已存在於 `silver.mv_fact_ui_task_details`)
以下所有欄位皆已實作，可直接供應給前端 API 或 Superset 使用。

| 業務需求欄位 | 對應的實體欄位 (`silver.mv_fact_ui_task_details`) | 備註說明 |
| :--- | :--- | :--- |
| **流程ID** | `proc_inst_id` | Flowable 流程實例 ID |
| **該節點是否 bypass** | `is_excluded` | 1 表示被排除 (Bypass)，可搭配 `exclude_reason` 顯示原因 (如 `system_bypass`, `auto_complete`) |
| **接單人員工號** | `assignee_code` | 系統中的 `ASSIGNEE_` 帳號/工號 |
| **接單人員帳號** | `assignee_code` | 在目前的系統中，工號與帳號通常是同一個欄位 (`ASSIGNEE_`) |
| **接單人員姓名** | `assignee_name` | 透過 HR 系統轉換的中文姓名 |
| **製造廠區** | `plant` | 例如 `WJ2` |
| **製造產品廠** | `factory` | 例如 `NBU` |
| **生產區域** | `region` | 例如 `CNE` |
| **線體** | `line` | 例如 `E5` |
| **任務創建時間** | `task_start_time` | 節點被觸發開出來的時間 |
| **接單時間** | `task_claim_time` | 使用者點擊/認領任務的時間 (已過濾 1970 假日期) |
| **完工時間** | `task_end_time` | 任務被送出完成的時間 (已過濾 1970 假日期) |
| **L5任務ID** | `task_id` | Flowable 原生任務 ID (`ID_`) |
| **L5任務編號** | `task_definition_key` | 任務定義代碼 (例如 `V3_Task_01`) |
| **L5任務名稱** | `task_name` | 任務的顯示名稱 |
| **工單號碼 (必要)** | `mo_number` | 流程變數中的工單號 |
| **L5任務狀態** | `task_status` | 系統動態判定的 Todo / Doing / Done |
| **L4流程名稱** | `l4_process_name` | 透過 `procdef` 關聯出的完整流程定義名稱 |
| **SAP PLANT** | `sap_plant` | 來自客製化表單變數 `sapPlant` |
| **SAP PRODUCTGROUP** | `sap_product_group` | 來自客製化表單變數 `sapProductGroup` |
| **棧板** | `pallet` | 來自客製化表單變數 `pallet` |
| **轉倉單據** | `transfer_no` | 來自客製化表單變數 `transferNo` |
| **Qblock事件編號** | `qblock_event_id` | 來自客製化表單變數 `qBlockEventId` |
| **不良序號** | `defect_sn` | 來自客製化表單變數 `defectSn` |
| **機種名稱** | `model_name` | 來自客製化表單變數 `modelName` |
| **配送區域** | `delivery_area` | 來自客製化表單變數 `deliveryArea` |
| **排程號碼** | `schedule_number` | 來自客製化表單變數 `scheduleNumber` |

---

## 🟡 2. 可透過現有欄位計算或推導 (Silver 有素材)
以下欄位不需要擴充底層 ETL，但需要在建立 View、Cube.js 或前端查詢時進行簡單的動態運算。

| 業務需求欄位 | 建議的處理/對應方式 | 備註說明 |
| :--- | :--- | :--- |
| **流程節點持续時間min** | 計算: `dateDiff('minute', task_start_time, task_end_time)` | 從「任務開出」到「完工」的總經過時間 |
| **流程節點處理時間min** | 計算: `dateDiff('minute', task_claim_time, task_end_time)` | 從「人員點開」到「完工」的實際操作時間 |
| **時間** | 對應: `task_start_date` 或 `snapshot_date` | 指該任務的「歸屬日期 (開單日)」 |
| **L4流程編號** | 對應: `vx_type` | 系統目前定義 V1, V2, V3 作為大流程分類 |

---

## ✅ 3. 實作架構歷程 (Implementation Architecture)

為避免影響現有 KPI 運算效能與底層結構，本專案採用**獨立明細表架構**。我們**不更動**核心的 `silver.mv_varinst_pivoted` 與 `silver.mv_fact_task_vx`，而是專為前端明細需求建立一套全新的獨立表結構：

#### 1. 建立專用的變數轉置視圖 (New Pivoted View)
新建一個 View，例如 `silver.mv_ui_varinst_pivoted`，專門用於轉置前端需要的這 9 個變數。
```sql
CREATE VIEW silver.mv_ui_varinst_pivoted AS
SELECT 
    PROC_INST_ID_,
    max(case when NAME_ = 'modelName' then TEXT_ end) AS ui_modelName,
    max(case when NAME_ = 'sapPlant' then TEXT_ end) AS ui_sapPlant,
    max(case when NAME_ = 'scheduleNumber' then TEXT_ end) AS ui_scheduleNumber,
    -- (其餘 6 個變數以此類推)
FROM bronze.bpm_act_hi_varinst
GROUP BY PROC_INST_ID_;
```

#### 2. 建立專用的 UI 明細寬表 (New UI Detail Table)
新建一張全新的實體明細表（例如 `silver.mv_fact_ui_task_details`），專供前端查詢。
撰寫新的 ETL 腳本（例如 `backfill_ui_details.sql`），將資料整合：
1.  **基礎打底**：直接從 `silver.mv_fact_task_vx` 取出現有已整理好的基礎 21 個欄位 (含 Bypass、五階、中英文名等)。
2.  **JOIN 流程變數**：與新建的 `silver.mv_ui_varinst_pivoted` 關聯，帶入上述的 9 個客製化表單變數。
3.  **JOIN 流程名稱**：與 `bronze.bpm_act_re_procdef` 關聯，帶出 `NAME_` 作為 **L4流程名稱**。

#### 3. 效益與後續開發
透過獨立的 `silver.mv_fact_ui_task_details` 表：
*   **安全隔離**：不干擾現有的 `silver.mv_fact_task_vx`，保證原本的 V4 KPI 結算速度與邏輯不受影響。
*   **專款專用**：未來若前端還要新增其他表單欄位，只要擴充這張 UI 專用表即可，架構極度乾淨。
