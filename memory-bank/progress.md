# 專案進度 - DMP Flowable

## 已完成里程碑

### 2026-04-14 (今日進度 - 實體化金層架構轉換與高併發效能驗收) [DONE]
- 🚀 **實體化金層架構 (Physical Gold Layer) 轉換完成**:
    - 成功自舊有的「動態視圖 (MVIEW)」轉變為實體化金層架構。
    - 徹底解除 Server 76 營運環境受限下的 OOM 與 Timeout 效能瓶頸。
- 📊 **高併發效能壓測驗收 (ClickHouse-Benchmark)**:
    - QPS 大幅提升逾 8 倍 (達 84.58)，Peak RAM 下降逾 98% (降至 < 5 MiB)。
    - 完成 10、50、100 並發極限負載測試，P99 延遲穩固於 0.61 秒。
    - 100 併發高壓下系統佇列機制啟動防禦成功，保障系統可用率 100%。
- 📚 **技術文件標準化與 ETL 腳本釐清**:
    - 產出 `Physical_Gold_Benchmark_Report.md` 與對應的壓測手冊。
    - 重新梳理 `execute_etl.py` 的運作路徑。
    - 以 Mermaid 語法大幅重構架構圖，完備資料血緣、Watermark 及 Checkpoint 等運作流程。
- 🛡️ **資安掃描結果溯源**:
    - 釐清了 `scripts/security_scan_results` 底層 Fortify 資安報告來源與生成。

### 2026-04-07 (今日進度 - 技術文件雙軌化與 ODBC 規格化) [DONE]
- 📚 **技術文件架構重整**:
    - 建立 `docs/legacy/` 資料夾，完整歸檔所有基於 JDBC Bridge 的歷史文件。
    - 將 ODBC 版技術文件提升為標準命名的現行文件 (`DMP_Flowable_Technical_Documentation.md`)。
    - 達成「JDBC 歷史可查、ODBC 現行主導」的文件管理模式。
- 🚀 **ODBC 高品質文件產出**:
    - 完成 `docs/01_architecture/Architecture_Overview.md` (Version 5.0) 的全版更新。
    - 新增 `docs/01_architecture/ClickHouse_ODBC_Setup.md` 專項手冊。
    - 更新 `docs/02_deployment/` 下的所有操作指導書以貼合現行架構。
- 🔧 **Silver/Gold 層資料全面重建**:
    - 完成從 2025-01-01 到 2026-04-07 的完整 Backfill。
    - 採用 `--low-ram` 與 `--step-days 10` 分段運算，確保 Server 76 穩定執行。
- ✅ **關鍵 Bug 與 Schema 修復**:
    - 修正 `backfill_silver.sql` 別名衝突。
    - 補齊 `bronze.common_hr_employee` 的 `EmpName` 欄位並重刷資料。

### 2026-04-02 (昨日進度 - Bronze 層優化完成與效能驗證) [DONE]
- 🚀 **Bronze 層優化全面完成**:
    - 完成 Bronze 資料庫重建，應用所有優化設定
    - 清除 ops_metrics checkpoint，重新執行完整 ETL pipeline
    - 驗證優化後的 Bronze → Silver → Gold 資料轉換
- 📊 **ETL 效能比較分析**:
    - **Silver 層改善**:
        - silver_varinst_pivoted: 5.56秒 → 5.45秒 (+1.95%)
        - silver_facts: 17.44秒 → 15.43秒 (+11.54%)
        - silver_exclusion: 1.18秒 → 0.96秒 (+18.94%)
    - **Gold 層效能下降**:
        - gold_milestone: 2.34秒 → 5.92秒 (-153%)
        - gold_acc: 2.11秒 → 3.95秒 (-87%)
    - **整體效能**: -10.35% (29.63秒 → 32.70秒)

### 2026-04-01 (進度 - 專案架構精煉與 Memory Bank 更新) [DONE]
- 📝 **Memory Bank 全面更新**:
    - 修正專案架構圖，移除錯誤的 Airflow DAG 描述。
    - 同步最新的 ODBC 技術決策與目錄結構。
- 🌍 **腳本國際化與清理**:
    - 完成核心腳本 (`init_pipeline.sh`, `daily_etl_wrapper.sh`) 的英文翻譯。

(以下省略歷史進度...)

## 進行中的工作

### 2026-04-07
- ✅ 技術文件雙軌化 (Dual-Layering) 完成
- ✅ ODBC 規格化手冊完備
- ✅ Silver/Gold 全面重建完成
- ✅ HR 資料補全驗證完成

### 2026-04-14
- ✅ 實體化金層架構 (Physical Gold Layer) 壓測與驗證完畢
- ✅ 技術設計書標準化與架構 (API 併發/ETL排程) 釐清完成
- ✅ 資安掃描報告溯源確認
- [ ] 持續觀察實際上線後的業務查詢與列隊穩定度

### 2026-04-15 (今日進度 - VTYPE 分類邏輯簡化完成) [DONE]
- 🔧 **VTYPE 分類規則簡化**:
    - 移除規則 1 (DG3 + 工單號) - 驗證為冗餘
    - 移除規則 2 (NPE + 工單號) - 驗證為冗餘
    - 保留規則 3 (僅工單號) 並重新編號為規則 1
    - 工單號列表：'196','199','200','210','212','213'
- 📊 **規則重疊驗證**:
    - 全域驗證：規則 1 和 2 的 323,486 筆資料 100% 被規則 3 涵蓋
    - 特定線體驗證 (CNS DG3 SMT ST02)：5,179 筆資料無差異
    - 驗證結論：可安全移除規則 1 和 2
- ✅ **SQL 更新完成**:
    - 更新 `sql/etl/dml/backfill_silver.sql`
    - 簡化 VTYPE 分類邏輯
    - 提升可讀性和維護性
