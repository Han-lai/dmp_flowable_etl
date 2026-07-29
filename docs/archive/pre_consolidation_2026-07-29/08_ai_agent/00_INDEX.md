# AI Knowledge Base — 入口與全專案知識地圖

**建立**: 2026-07-03（Fable 5 Project Intelligence Session）
**定位**: 本目錄（`docs/08_ai_agent/`）是給 **AI Agent** 的知識層：導航、已驗證事實、踩坑錄、工作規範。人類向的深度技術文件在 `docs/00~07`，兩者互補不重複。

---

## 本知識庫（依閱讀順序）

| 文件 | 內容 | 何時讀 |
|---|---|---|
| [01_Project_Assessment.md](01_Project_Assessment.md) | 專案定位、風險排序、已知不一致清單（AI 最易誤判處） | 首次接觸專案 |
| [02_Code_Intelligence.md](02_Code_Intelligence.md) | 已驗證的端到端資料流、每個模組的職責/機制/注意事項、重要度分級 | 動任何程式碼前 |
| [03_Knowledge_Base.md](03_Knowledge_Base.md) | 技術選型理由、業務術語表、ClickHouse 慣用模式、環境變數表 | 看不懂術語/模式時 |
| [04_Development_Guide.md](04_Development_Guide.md) | 命名慣例、修改流程鐵律、測試方法、Review checklist | 寫程式碼前 |
| [05_Troubleshooting.md](05_Troubleshooting.md) | 全部歷史事故與根因（同步/ETL/查詢/監控/對帳五類） | 遇到任何異常先搜這裡 |
| [06_AI_Agent_Workflow.md](06_AI_Agent_Workflow.md) | Session 開場儀式、真相優先序、禁區、文件維護協議、開放中工作 | 每個 Session 開始 |
| [07_Handover_Addendum.md](07_Handover_Addendum.md) | 交接補充（指向既有交接手冊 + 本次 Session 的差異發現） | 交接時 |

## 全專案知識地圖（Knowledge Map）

```
入口層
├── CLAUDE.md（根目錄）················ AI 自動載入：規則 + 指令 + 導航
├── docs/08_ai_agent/00_INDEX.md ····· 本文件（AI 知識庫入口）
└── docs/00_INDEX.md ················· 人類文件庫入口（⚠ 部分連結檔名過時）

即時狀態層（最常變動，每 Session 必讀）
├── memory-bank/activeContext.md ····· 當前焦點、待辦、未 commit 事項 ★
├── memory-bank/progress.md ·········· 里程碑編年史（含事故詳情）
└── ops：execute_etl.py --status ····· 生產環境即時水位線/checkpoint

架構與設計層
├── docs/01_architecture/Architecture_Overview.md ··· 系統架構總覽（含 ASCII 圖）
├── docs/01_architecture/ClickHouse_ODBC_Setup.md ··· ODBC 同步規格
├── memory-bank/systemPatterns.md ··················· 關鍵技術決策記錄
└── docs/08_ai_agent/02_Code_Intelligence.md ········ 已驗證模組地圖 ★

業務邏輯層（KPI 的真相）
├── sql/etl/dml/*.sql ······························· 唯一真相 ★
├── docs/03_metrics/01_Metrics_and_Data_Definitions.md 指標語意定義
├── docs/03_metrics/02_ETL_Transformation_Pipeline.md  7+1 階管線 SQL 解說
├── docs/03_metrics/05_Calculation_Logic_Changelog.md  計算邏輯變更史
└── docs/03_metrics/06_V3_Summary_Backfill_Impl.md ··· V3 歷史回填實作

開發與維運層
├── docs/03_metrics/04_Developer_Guide_New_Metrics.md  新增指標 SOP（人類向深度版）
├── docs/06_Data_Engineer_Handover.md ··············· 完整開發維運手冊（10 部分）
├── docs/07_ETL_Execution_Guide_For_Beginners.md ····· 新手執行指南
├── docs/02_deployment/Deployment_Guide.md ··········· 部署手冊
└── docs/08_ai_agent/04 + 05 + 06 ··················· AI 向規範/踩坑/流程 ★

服務層
├── docs/04_serving/CubeJS_Semantic_Layer.md ········· Cube 語意層
├── docs/04_serving/API_DOCUMENTATION.md ············· FastAPI 規格
├── docs/04_serving/Superset_Chart_Guide.md ·········· Superset 整合
└── cube/model/cubes/README_L5_DASHBOARD_CUBE.md ····· Cube 模型說明

監控層
├── docs/05_monitoring/grafana_dashboard_setup.md ···· Grafana 配置（⚠ 含內部 IP）
├── docs/05_monitoring/Physical_Gold_Benchmark_Report.md 壓測報告
└── docs/05_monitoring/ClickHouse_Benchmark_Guide.md · 壓測 SOP

歷史/考古層（不要依此實作）
├── .kiro/specs/ ····································· 舊需求規格（部分與現行衝突）
├── archive/ + docs/archive/ ························· V4 演進過程封存
├── memory-bank/productContext.md ···················· 部分段落過時
└── prd_audit/ + prd_mssql/ ·························· 對帳一次性產物
```

★ = 未來 AI Session 的高頻文件。

## 維護規則

本知識庫的更新協議見 [06_AI_Agent_Workflow.md](06_AI_Agent_Workflow.md) §6。核心原則：**程式碼是唯一真相，文件腐化時修文件；每個事實標 ✅已驗證/⚠推測/❓未確認。**
