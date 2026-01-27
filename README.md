# DMP Flowable 流程分析系統

基於 ClickHouse → Cube.js → Superset 的完整資料管道，專注於 L5 任務完成率分析。

## 🏗️ 系統架構

```
MSSQL → JDBC Bridge → ClickHouse → Cube.js → Superset
                      ├── Bronze: 原始資料
                      ├── Silver: 維度補齊 + 清理
                      └── Gold: 業務彙總
```

## 🚀 快速開始 (5 分鐘)

### 新人部署
```bash
# 1. 取得專案
git clone [repository_url]
cd dmp_flowable

# 2. 一鍵部署
python deploy.py

# 3. 驗證安裝
python scripts/setup/verify_installation.py
```

### 手動部署
請參考 `GETTING_STARTED.md` 詳細指南

### 1. ClickHouse 資料層
```bash
# 執行 DDL 套件 (按順序)
clickhouse-client < clickhouse/ddl/00_databases.sql
clickhouse-client < clickhouse/ddl/10_bronze_sources.sql
clickhouse-client < clickhouse/ddl/20_silver_views_and_mviews.sql
clickhouse-client < clickhouse/ddl/30_gold_views_and_mviews.sql
clickhouse-client < clickhouse/ddl/40_validation_queries.sql

# 驗證管道
python clickhouse/scripts/verify_mview_pipeline_completion.py
```

### 2. Cube.js 語意層
```bash
cd cube
docker-compose up -d
```

### 3. 驗證系統
```bash
python clickhouse/scripts/verify_mssql_clickhouse_reconciliation.py
```

## ✨ 核心功能

- **維度補齊邏輯**: VARINST 優先，MDM 補齊，標記資料來源
- **ISO Week 合規**: W-pattern 和 Dn-1 動態時間邏輯
- **100% 一致性**: MSSQL vs ClickHouse 完全對帳
- **V1/V3 歸屬**: 315% 工單規則和任務定義鍵邏輯
- **L5 任務分析**: 完整的任務完成率儀表板

## 📁 專案結構

```
dmp_flowable/
├── GETTING_STARTED.md          # 新人快速開始指南 ⭐
├── ARCHITECTURE.md             # 系統架構說明 ⭐
├── deploy.py                   # 一鍵部署腳本 ⭐
│
├── config/                     # 設定檔 ⭐
│   └── environments/          # 環境變數管理
├── scripts/                   # 執行腳本 (重新分類) ⭐
│   ├── setup/               # 安裝設定
│   ├── sync/                # 資料同步
│   ├── validation/          # 驗證測試
│   ├── maintenance/         # 維護工具
│   └── utils/               # 工具腳本
├── sql/ddl/                   # DDL 腳本 (按順序執行)
├── cube/model/cubes/          # Cube.js 資料模型
├── docker/                    # Docker 基礎設施
└── docs/                      # 完整文件
```

**詳細結構**: 請參考 `PROJECT_STRUCTURE.md`

## 📚 重要文檔

### 新人必讀
- **`GETTING_STARTED.md`** - 5分鐘快速部署指南
- **`ARCHITECTURE.md`** - 深度系統架構說明
- **`PROJECT_STRUCTURE.md`** - 專案結構說明

### 進階指南
- **`REBUILD_GUIDE.md`** - 完整重建指南
- **`docs/metric_definitions.md`** - 指標定義 (v1.4)
- **`docs/varinst_to_mdm_mapping_specification.md`** - 維度映射規格

### 歷史記錄
- **`ARCHIVE/memory/project_progress_2026_01_26.md`** - 最新進度記錄

## 🎯 專案狀態 (2026-01-26)

**✅ 已完成核心任務**:
1. **L5 Metrics DDL Package**: 完整的 Bronze → Silver → Gold DDL 套件
2. **維度補齊邏輯**: VARINST 優先，MDM 補齊，標記資料來源
3. **Cube.js 資料模型**: 已更新使用新的 Gold layer 表格
4. **ISO Week 合規性**: W-pattern 和 Dn-1 動態邏輯實作
5. **MSSQL vs ClickHouse 一致性**: 100% 一致性驗證通過

**🏗️ 技術架構**:
- **資料血緣**: 完全透明，使用原生 Flowable 表 (ACT_* 系列)
- **維度補齊**: VARINST 優先，MDM 補齊，完整資料來源追蹤
- **時間邏輯**: 統一的 OR 條件邏輯，確保 MSSQL 和 ClickHouse 一致
- **V1/V3 歸屬**: 工單號規則優先，任務定義鍵其次

**📈 驗證結果**:
- **測試案例**: CNE-WJ2-NBU-E5 (V1: 25 任務, V3: 1 任務, V2: 0 任務)
- **完成率**: V1 任務完成率 7.7% (TODO: 19, DOING: 5, DONE: 2)
- **維度交換**: CNE-WJ2-NBU-E5 → CNE-NBU-WJ2-E5 (成功)
- **資料來源**: MDM_PRIMARY (100% 來自 MDM 表)

## 🔧 常用指令

### 資料同步
```bash
# 初始資料同步
python scripts/sync/sync_initial_data.py

# 增量同步
python scripts/sync/sync_incremental.py

# 全量同步
python scripts/sync/sync_to_clickhouse.py
```

### 驗證測試
```bash
# 資料完整性驗證
python scripts/validation/verify_data_integrity.py

# MSSQL vs ClickHouse 對帳
python scripts/validation/verify_mssql_clickhouse_reconciliation.py

# 管道完整性驗證
python scripts/validation/verify_mview_pipeline_completion.py
```

### 維護工具
```bash
# 備份和更新 Silver MVIEW
python scripts/maintenance/backup_and_update_silver_mview.py

# 更新 Gold 維度
python scripts/maintenance/execute_gold_dimension_update.py

# 生產環境測試
python scripts/maintenance/production_environment_test.py
```

---

**Last Updated**: 2026-01-28  
**Version**: 2.0 (標準化重整完成)  
**Status**: 新人可從零開始部署