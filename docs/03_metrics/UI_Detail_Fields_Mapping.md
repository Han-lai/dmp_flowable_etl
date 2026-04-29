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
| **文件編號**: 03-MTR-002  
**版本**: 4.3  
**最後更新**: 2026-04-29  
**狀態**: 實作規格調整 (Refactoring)  | 例如 `E5` |
| **任務創建時間** | `task_start_time` | 節點被觸發開出來的時間 |
| **接單時間** | `task_claim_time` | 使用者點擊/認領任務的時間 (已過濾 1970 假日期) |
| **完工時間** | `task_end_time` |### 2.1 基礎維度與時效指標 (Dimensions & Timing)

| 報表欄位名稱 | 來源表 (ClickHouse) | 來源欄位 / 計算邏輯 | 備註 |
| :--- | :--- | :--- | :--- |
| **L4 流程編號** | `ACT_HI_PROCINST` | `BUSINESS_STATUS_` | **修正：不再使用 INST_ID** |
| **L4 流程名稱** | `ACT_HI_PROCDEF` | `NAME_` | |
| **流程節點名稱** | `ACT_HI_TASKINST` | `NAME_` | |
| **流程節點持續時間 (min)** | 計算欄位 | `(task_end_time - task_start_time) / 60` | 以分鐘計 |
| **流程節點處理時間 (min)** | 計算欄位 | `(task_end_time - task_claim_time) / 60` | 以分鐘計 |
| **時間欄位 (Time)** | `ACT_HI_VARINST` | `TEXT_` (當 `NAME_ = 'time'`) | **純業務欄位展示** |
| **實際快照日期** | `ACT_HI_TASKINST` | `toDate(START_TIME_)` | |
| **任務狀態 (日/週/月)** | `Calculated` | `status_daily / weekly / monthly` | 對接 V4 結算邏輯 |

### 2.2 業務擴充變數 (BPM Business Variables)
*來源均為 `bronze.bpm_act_hi_varinst`，透過 PROC_INST_ID_ 進行轉置。*

| 報表欄位名稱 | 變數名稱 (NAME_) | 備註 |
| :--- | :--- | :--- |
| **工單號碼** | `moNumber` | |
| **排程號碼** | `scheduleNumber` | |
| **SAP 廠區** | `sapPlant` | |
| **SAP 產品組** | `sapProductGroup` | |
| **棧板號** | `pallet` | |
| **移庫單號** | `transferNo` | |
| **Q-Block 事件 ID** | `qBlockEventId` | |
| **不良品 SN** | `defectSn` | |
| **機種名稱** | `modelName` | |
| **出貨區域** | `deliveryArea` | | **機種名稱** | `model_name` | 來自客製化表單變數 `modelName` |
| **配送區域** | `delivery_area` | 來自客製化表單變數 `deliveryArea` |
| **排程號碼** | `schedule_number` | 來自客製化表單變數 `scheduleNumber` |

---

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
新建或更新 `silver.mv_ui_varinst_pivoted`，包含所有業務變數與自定義時間欄位。
```sql
CREATE OR REPLACE VIEW silver.mv_ui_varinst_pivoted AS
SELECT 
    PROC_INST_ID_,
    max(case when NAME_ = 'time' then TEXT_ end) AS ui_time_field, -- 新增時間欄位
    max(case when NAME_ = 'moNumber' then TEXT_ end) AS ui_moNumber,
    max(case when NAME_ = 'modelName' then TEXT_ end) AS ui_modelName,
    -- ... (其餘變數)
FROM bronze.bpm_act_hi_varinst
GROUP BY PROC_INST_ID_;
```

#### 2. 建立專用的 UI 明細寬表 (New UI Detail Table)
實作邏輯調整：
1.  **基礎打底**：從 `silver.mv_fact_task_vx` 取出基礎線體維度。
2.  **時效計算**：利用 `task_start_time`, `task_claim_time`, `task_end_time` 進行 `dateDiff` 分鐘運算。
3.  **L4 編號修正**：JOIN `bronze.bpm_act_hi_procinst` 取出 `BUSINESS_STATUS_`。
4.  **業務資料**：JOIN `silver.mv_ui_varinst_pivoted` 帶入業務變數與 `ui_time_field`。

#### 3. 效益與核心規範
*   **數據唯一性**：所有時間標籤以 `VARINST` 或計算結果為準，不再依賴 Task 表的推導狀態。
*   **流程分類**：`PROCINST` 僅作為流程屬性（如 L4 編號）的來源，不參與時效邏輯。
*   **獨立性**：此架構確保 KPI 計算與 UI 展示完全解耦。

---

## 🔵 4. 完整明細表欄位清單 (Full Field List)

以下為 `silver.mv_fact_ui_task_details` 最終實作的所有欄位，共計 34 欄：

### 4.1 基礎識別與流程資訊
| 欄位名稱 (Physical Name) | 業務名稱 (Display Name) | 來源說明 |
| :--- | :--- | :--- |
| `task_id` | 任務 ID | Flowable 原生 ID |
| `proc_inst_id` | 流程實例 ID | Flowable 原生 ID |
| `l4_process_id` | **L4 流程編號** | `ACT_HI_PROCINST.BUSINESS_STATUS_` |
| `l4_process_name` | L4 流程名稱 | `ACT_HI_PROCDEF.NAME_` |
| `task_definition_key` | 任務定義代碼 | 例如 `V3_Task_01` |
| `task_name` | 任務名稱 | 節點顯示名稱 |

### 4.2 時效指標與時間軸
| 欄位名稱 (Physical Name) | 業務名稱 (Display Name) | 計算邏輯 / 來源 |
| :--- | :--- | :--- |
| `task_start_time` | 任務開始時間 | 基礎時間戳記 |
| `task_claim_time` | 任務領取時間 | 基礎時間戳記 |
| `task_end_time` | 任務完工時間 | 基礎時間戳記 |
| `duration_min` | **節點持續時間 (min)** | `(end - start) / 60` |
| `processing_time_min` | **節點處理時間 (min)** | `(end - claim) / 60` |
| `ui_time_field` | **時間欄位 (Time)** | `VARINST.time` (業務自定義) |

### 4.3 業務擴充變數 (Pivoted)
| 欄位名稱 (Physical Name) | 業務名稱 (Display Name) | 來源變數 (NAME_) |
| :--- | :--- | :--- |
| `mo_number` | 工單號碼 | `moNumber` |
| `schedule_number` | 排程號碼 | `scheduleNumber` |
| `sap_plant` | SAP 廠區 | `sapPlant` |
| `sap_product_group` | SAP 產品組 | `sapProductGroup` |
| `pallet` | 棧板號 | `pallet` |
| `transfer_no` | 移庫單號 | `transferNo` |
| `qblock_event_id` | Q-Block 事件 ID | `qBlockEventId` |
| `defect_sn` | 不良品 SN | `defectSn` |
| `model_name` | 機種名稱 | `modelName` |
| `delivery_area` | 出貨區域 | `deliveryArea` |

### 4.4 製造維度與執行者
| 欄位名稱 (Physical Name) | 業務名稱 (Display Name) | 來源說明 |
| :--- | :--- | :--- |
| `vx_type` | 流程類型 | V1 / V2 / V3 |
| `region` | 區域 | 例如 CNE |
| `plant` | 廠區 | 例如 WJ2 |
| `factory` | 工廠 | 例如 NBU |
| `line` | 線體 | 例如 E5 |
| `assignee_code` | 執行者工號 | |
| `assignee_name` | 執行者姓名 | |

### 4.5 狀態結算與稽核 (對齊 KPI)
| 欄位名稱 (Physical Name) | 業務名稱 (Display Name) | 說明 |
| :--- | :--- | :--- |
| `task_status` | 即時狀態 | 當前系統狀態 |
| `status_daily` | 日結算狀態 | 開單當日 23:59 結算 |
| `status_weekly` | 週結算狀態 | 該週週日 23:59 結算 |
| `status_monthly` | 月結算狀態 | 該月月底 23:59 結算 |
| `is_excluded` | 是否排除 | 1=排除 / 0=包含 |
| `exclude_reason` | 排除原因 | 例如 system_bypass |
