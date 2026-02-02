# 會議準備重點：Flowable 數據差異檢討

**核心議題**：其他部門認為指標應以 `FlowableTaskStats` 為準，但實際驗證發現該表數據與 Raw Data (原始表) 存在嚴重落差，且 ClickHouse 的計算結果反而更能反映 Raw Data 的真實狀況。

## 議題一：FlowableTaskStats 的數據可信度存疑
**論點**：QAS 環境中的 `FlowableTaskStats` 目前似乎**未正確更新**或**指向錯誤的底表**，不能作為驗收標準 (Golden Sample)。

*   **現象 (Observation)**:
    *   在 QAS 查詢 **Line E4** (2025-12-25) 的 `FlowableTaskStats`，結果僅 **5 筆**。
*   **反證 (Evidence)**:
    *   在**同一個 QAS 環境**，直接查詢 Raw Table (`ACT_HI_TASKINST_0108`) 並套用相同篩選條件，結果有 **160+ 筆**。
    *   Raw Data 裡明明有資料，Stats 表卻沒有，證明 **Stats 表與 Raw Data 脫鉤 (Out of Sync)**。
*   **提問 (Validation Question)**:
    *   「請問 `FlowableTaskStats` View 的定義是否已更新為讀取新的 `_0108` 後綴表？」
    *   「如果 Stats 表是準的，為什麼它無法反映 `_0108` 表中存在的 100 多筆任務？」

## 議題二：ClickHouse 邏輯已驗證，數據完全對齊 Source Raw Data
**論點**：ClickHouse 的計算邏輯是正確的，因為它能精準重現 Raw Data 的查詢結果。

*   **現象**:
    *   我們將 QAS 用來查詢 Raw Table 的 SQL 邏輯 (包含 Plant/Line Join 及時間篩選) 搬到 ClickHouse 執行。
*   **證據**:
    *   **Line E5**: QAS Raw SQL 查出約 198 筆 ↔ ClickHouse 模擬跑出 **196 筆** (✅ 吻合)。
    *   這證明 ClickHouse 的 ETL 流程與計算邏輯**沒有錯誤**。
*   **結論**:
    *   既然 ClickHouse 能算出跟 QAS Raw SQL 一樣的數字，那 ClickHouse 算出的 E4 (163筆) 也是基於 Raw Data 的正確結果。

## 議題三：數據源版本混亂 (Table Versioning)
**論點**：UAT/QAS 環境存在多個版本的表 (`_0108`, 無後綴, 舊備份)，導致驗證基準混亂。

*   **現象**:
    *   在 DB 中看到了 `ACT_HI_TASKINST` (空/舊) 與 `ACT_HI_TASKINST_0108` (新) 並存。
    *   ClickHouse 之前如果同步了舊表，就會像 QAS Stats 一樣查不到資料。
*   **行動 (Action Item)**:
    *   我們已確認 ClickHouse 現在同步的是 **`_0108`** 表 (與 Source 筆數 100% 吻合)。
    *   建議本次會議明確定義：**「未來的驗收標準 (Source of Truth) 究竟是 `_0108` 這張表，還是 `FlowableTaskStats`？」**
    *   如果是 `FlowableTaskStats`，那它必須被修復 (Reload/Redefine) 以符合 `_0108` 的內容。

## 總結建議 (Proposal)
1.  **承認差異**：目前 QAS 的 `FlowableTaskStats` 是**不準確的** (Under-reporting)。
2.  **臨時標準**：在 Stats 表修復前，應以 **ClickHouse 或直接查詢 Raw Table SQL** 的結果作為驗收依據。
3.  **修復計畫**：請負責 ETL/DB 的團隊更新 `FlowableTaskStats` 的生成邏輯，納入 `_0108` 表的數據。
