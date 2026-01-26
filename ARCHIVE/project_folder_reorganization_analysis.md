# 專案資料夾重組分析報告

**分析日期**: 2026-01-26  
**分析目標**: 整理專案資料夾，只保留「可重建 ClickHouse → Cube.js → Superset」所需檔案  
**重建管道**: ClickHouse SQL + View/MVIEW + 手動排程（無 Airflow）

---

## 🎯 重建管道架構

```
ClickHouse (核心資料層)
├── Bronze: 原始資料表 (MSSQL 同步)
├── Silver: 維度補齊 + 清理 (MVIEW)
└── Gold: 業務彙總 (Table/View)
    ↓
Cube.js (語意層)
├── 資料模型定義
└── 預聚合配置
    ↓
Superset (視覺化層)
├── 儀表板配置
└── 圖表定義
```

---

## 📋 檔案分類標準

### Keep (必留) - 重建必需檔案
- ClickHouse DDL 和核心 SQL
- Cube.js 資料模型
- 重建驗證腳本
- 核心架構文檔

### Archive (留存但不參與重建) - 歷史記錄和分析
- 開發過程記錄
- 驗證分析報告
- 舊版本檔案
- 調試腳本

### Remove (可移除) - 非必要檔案
- 臨時檔案
- 重複檔案
- 過時檔案

---

## 📊 檔案分類結果

### ✅ Keep (必留檔案) - 重建核心

#### ClickHouse 核心 DDL
```
sql/ddl/00_databases.sql                    # 資料庫建立
sql/ddl/10_bronze_sources.sql               # Bronze 層表格
sql/ddl/20_silver_views_and_mviews.sql      # Silver 層 MVIEW (維度補齊)
sql/ddl/30_gold_views_and_mviews.sql        # Gold 層表格 (業務彙總)
sql/ddl/40_validation_queries.sql           # 驗證查詢
sql/ddl/validation_acceptance_test.sql      # 驗收測試
```

#### Cube.js 資料模型
```
cube/model/cubes/cube_gold_l5_task_completion.js    # L5 任務完成率模型
cube/model/cubes/cube_l5_dashboard_summary.js       # L5 儀表板摘要模型
cube/.env.example                                   # 環境變數範例
cube/docker-compose.yml                             # Cube.js 容器配置
cube/README.md                                      # Cube.js 說明
```

#### Docker 基礎設施
```
docker/docker-compose.yml                   # 主要容器編排
docker/clickhouse/                         # ClickHouse 配置
docker/README.md                           # Docker 說明
```

#### 核心驗證腳本
```
scripts/verify_mssql_clickhouse_reconciliation.py   # MSSQL-ClickHouse 對帳
scripts/verify_mview_pipeline_completion.py         # MVIEW 管道驗證
scripts/execute_end_to_end_pipeline.py             # 端到端管道執行
```

#### 核心架構文檔
```
docs/metric_definitions.md                          # 指標定義 (v1.4)
docs/varinst_to_mdm_mapping_specification.md       # 維度映射規格
docs/ARCHITECTURE_OVERVIEW.md                      # 架構總覽
README.md                                           # 專案說明
```

#### 專案配置
```
package.json                                        # Node.js 依賴
package-lock.json                                   # 依賴鎖定
```

### 📦 Archive (留存檔案) - 歷史記錄

#### 開發記錄和分析
```
ARCHIVE/memory/project_progress_2026_01_26.md      # 最新進度記錄
MSSQL_CLICKHOUSE_RECONCILIATION_SUCCESS.md         # 對帳成功記錄
REFACTOR_REPORT.md                                 # 重構報告
TODO_DATA_VALIDATION.md                           # 待辦驗證項目
```

#### 詳細技術文檔
```
docs/clickhouse_data_model_design.md               # ClickHouse 資料模型設計
docs/data_flow_guide.md                           # 資料流指南
docs/end_to_end_architecture_report.md            # 端到端架構報告
docs/manufacturing_five_level_data_lineage.md     # 製造五階資料血緣
docs/silver_gold_mapping_compliance_report.md     # Silver-Gold 映射合規報告
docs/mview_dimension_backfill_update_plan.md      # 維度補齊更新計劃
docs/superset_usage_guide.md                      # Superset 使用指南
docs/superset_l5_dashboard_guide.md               # L5 儀表板指南
```

#### 驗證和分析腳本
```
scripts/verify_cne_wj2_nbu_e5_task_status_2025_12_25_31.py  # 特定案例驗證
scripts/validate_silver_dimension_backfill.py               # 維度補齊驗證
scripts/execute_dimension_backfill_validation.py            # 維度補齊執行驗證
scripts/check_current_mview_architecture.py                 # MVIEW 架構檢查
validation_results/                                         # 驗證結果目錄
```

#### SQL 分析和修正
```
sql/validate_iso_week_compliance.sql               # ISO Week 合規驗證
sql/fix_iso_week_compliance.sql                   # ISO Week 修正
sql/compare_mssql_clickhouse_time_logic.sql       # 時間邏輯比較
sql/dimension_backfill_implementation.sql         # 維度補齊實作
sql/validate_dimension_backfill_logic.sql         # 維度補齊邏輯驗證
```

#### 歷史開發檔案
```
sql/create_gold_l5_dashboard_summary.sql          # Gold 層表格建立 (舊版)
sql/create_l5_dashboard_completion_table.sql      # L5 完成表建立 (舊版)
sql/11_create_silver_mviews_layer1.sql           # Silver Layer 1 (舊版)
sql/12_create_silver_mviews_layer2.sql           # Silver Layer 2 (舊版)
```

### 🗑️ Remove (可移除檔案) - 非必要

#### 臨時和測試檔案
```
temp_create_mview.sql                              # 臨時 MVIEW 建立
check_bronze_structure.py                         # Bronze 結構檢查 (一次性)
```

#### 重複和過時檔案
```
cube/model/cubes/cube_gold_user_utilization.js    # 使用者使用率模型 (非 L5 核心)
sql/02_create_bpm_tables.sql                      # BPM 表格建立 (已整合到 DDL)
sql/13_create_gold_mviews.sql                     # Gold MVIEW (已整合到 DDL)
```

#### 調試和開發工具
```
scripts/debug_*.py                                # 所有調試腳本
scripts/check_*.py                               # 檢查腳本 (非驗證用)
scripts/analyze_*.py                             # 分析腳本 (非核心)
scripts/find_*.py                                # 查找腳本 (開發用)
scripts/compare_*.py                             # 比較腳本 (除核心驗證外)
```

#### 日誌和快取
```
logs/                                             # 日誌目錄
__pycache__/                                      # Python 快取
node_modules/                                     # Node.js 模組 (可重新安裝)
.venv/                                           # Python 虛擬環境 (可重建)
```

---

## 🏗️ 建議的新資料夾結構

```
dmp_flowable/
├── README.md                           # 專案說明
├── package.json                        # Node.js 依賴
├── package-lock.json                   # 依賴鎖定
│
├── clickhouse/                         # ClickHouse 核心
│   ├── ddl/                           # DDL 腳本
│   │   ├── 00_databases.sql
│   │   ├── 10_bronze_sources.sql
│   │   ├── 20_silver_views_and_mviews.sql
│   │   ├── 30_gold_views_and_mviews.sql
│   │   ├── 40_validation_queries.sql
│   │   └── validation_acceptance_test.sql
│   └── scripts/                       # 核心驗證腳本
│       ├── verify_mssql_clickhouse_reconciliation.py
│       ├── verify_mview_pipeline_completion.py
│       └── execute_end_to_end_pipeline.py
│
├── cube/                              # Cube.js 語意層
│   ├── model/cubes/
│   │   ├── cube_gold_l5_task_completion.js
│   │   └── cube_l5_dashboard_summary.js
│   ├── .env.example
│   ├── docker-compose.yml
│   └── README.md
│
├── docker/                            # 基礎設施
│   ├── docker-compose.yml
│   ├── clickhouse/
│   └── README.md
│
├── docs/                              # 核心文檔
│   ├── metric_definitions.md          # 指標定義 (v1.4)
│   ├── varinst_to_mdm_mapping_specification.md
│   └── ARCHITECTURE_OVERVIEW.md
│
└── ARCHIVE/                           # 歷史記錄
    ├── development/                   # 開發過程
    ├── analysis/                     # 分析報告
    ├── validation/                   # 驗證結果
    └── legacy/                       # 舊版檔案
```

---

## ✅ 重建驗證清單

### Phase 1: ClickHouse 資料層
- [ ] 執行 DDL 套件 (00 → 10 → 20 → 30 → 40)
- [ ] 驗證 Bronze 層資料同步
- [ ] 驗證 Silver 層 MVIEW 建立和維度補齊
- [ ] 驗證 Gold 層業務彙總表
- [ ] 執行驗收測試

### Phase 2: Cube.js 語意層
- [ ] 部署 Cube.js 容器
- [ ] 載入資料模型定義
- [ ] 測試資料存取和預聚合
- [ ] 驗證指標計算正確性

### Phase 3: Superset 視覺化層
- [ ] 連接 Cube.js 資料源
- [ ] 建立 L5 儀表板
- [ ] 驗證圖表和篩選功能
- [ ] 端到端功能測試

### Phase 4: 整合驗證
- [ ] MSSQL vs ClickHouse 對帳 (100% 一致性)
- [ ] 維度補齊邏輯驗證 (VARINST 優先，MDM 補齊)
- [ ] ISO Week 時間合規性驗證
- [ ] 完整資料流測試

---

## 📈 預期效益

### 檔案數量減少
- **原始檔案**: ~200+ 檔案
- **Keep 檔案**: ~25 檔案 (核心)
- **Archive 檔案**: ~100 檔案 (保留)
- **Remove 檔案**: ~75 檔案 (移除)
- **減少比例**: 約 60% 檔案移除或歸檔

### 重建效率提升
- **明確的重建路徑**: ClickHouse → Cube.js → Superset
- **最小化依賴**: 只保留必要檔案
- **標準化流程**: DDL 套件 + 驗證腳本
- **文檔完整**: 核心架構和指標定義

### 維護成本降低
- **清晰的檔案結構**: 按功能分層組織
- **減少混淆**: 移除過時和重複檔案
- **專注核心**: 重建相關檔案集中管理
- **歷史保留**: 重要記錄歸檔保存

---

## 🚀 下一步行動

1. **執行重組**: 按照分類結果移動檔案
2. **建立新結構**: 創建建議的資料夾結構
3. **更新文檔**: 修正檔案路徑引用
4. **測試重建**: 驗證重建流程完整性
5. **建立 SOP**: 標準化重建操作程序

---

**分析完成時間**: 2026-01-26  
**分析者**: Kiro AI Assistant  
**狀態**: 準備執行重組