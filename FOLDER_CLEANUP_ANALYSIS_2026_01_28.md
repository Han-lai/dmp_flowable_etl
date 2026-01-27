# 專案資料夾整理分析報告 - 2026年1月28日

## 目前專案架構狀態

### ✅ 核心架構資料夾 (保留)

#### 1. **clickhouse/** - ClickHouse DDL 核心
- `clickhouse/ddl/` - 標準化 DDL 腳本 (6個核心檔案)
- `clickhouse/scripts/` - 核心驗證腳本 (3個)
- **狀態**: 已整理完成，保留

#### 2. **cube/** - Cube.js 資料模型
- `cube/model/cubes/` - L5 Dashboard 資料模型 (2個)
- `cube/.env.example`, `cube/docker-compose.yml`
- **狀態**: 核心功能，保留

#### 3. **docs/** - 核心文件
- 架構文件: `ARCHITECTURE_OVERVIEW.md`, `data_pipeline_diagram.md`
- L5 規格: `l5_dashboard_completion_specification.md`
- 維度對應: `manufacturing_five_level_data_lineage_updated.md`
- Superset 指南: `superset_*.md`
- **狀態**: 核心文件，保留

#### 4. **ARCHIVE/** - 已整理的歷史檔案
- 已分類整理的舊檔案
- **狀態**: 已整理完成，保留

### ⚠️ 需要整理的資料夾

#### 1. **scripts/** - 腳本過多且混亂 (95個檔案)

**🔧 核心腳本 (保留 - 15個)**:
```
# 連線和基礎驗證
- test_clickhouse_connection.py
- check_existing_tables.py
- verify_mssql_clickhouse_reconciliation.py
- verify_mview_pipeline_completion.py
- debug_superset_cne_wj2_nbu_e5_2025_12_25.py

# 維度補齊邏輯
- execute_silver_dimension_update.py
- execute_gold_dimension_update.py
- backup_and_update_silver_mview.py
- explain_mdm_mapping_logic.py

# 驗證和合規
- execute_mapping_compliance_validation.py
- execute_varinst_mdm_validation.py
- validate_silver_gold_mapping_compliance.py

# End-to-End 管道
- execute_end_to_end_pipeline.py
- verify_complete_architecture.py
- production_environment_test.py
```

**📦 移至 ARCHIVE/scripts/ (80個)**:
```
# 開發和測試腳本
- 所有 debug_*, diagnose_*, fix_*, force_*, recreate_* 開頭的檔案
- 所有 compare_*, verify_*_specific_date.py 特定測試
- 所有 create_*, deploy_*, rebuild_* 一次性執行腳本
- 所有 validate_*_specific.py 特定驗證腳本
```

#### 2. **sql/** - SQL 檔案過多且混亂 (40+個檔案)

**🔧 核心 SQL (保留 - 8個)**:
```
# DDL 標準檔案已移至 clickhouse/ddl/，這裡保留業務邏輯
- create_silver_dim_mfg_five_level.sql
- update_silver_dimension_backfill_logic.sql
- update_gold_dimension_backfill_logic.sql
- validate_dimension_backfill_logic.sql
- validate_varinst_mdm_mapping.sql
- validate_silver_gold_mapping_compliance.sql
- corrected_varinst_mdm_mapping_demo.sql
- END_TO_END_EXECUTION_GUIDE.md
```

**📦 移至 ARCHIVE/sql/ (30+個)**:
```
# 舊版本和測試檔案
- 所有 00_*, 01_*, 02_* 等編號檔案 (已有新版在 clickhouse/ddl/)
- 所有 fix_*, test_*, create_*_test.sql
- 所有 12_create_silver_mviews_layer2_*.sql 變體版本
- 所有時間戳檔案 create_*_20260123_*.sql
```

#### 3. **logs/** - 日誌檔案 (8個)

**🔧 保留重要日誌 (3個)**:
```
- data_inconsistency_analysis_20260123_143000.md (重要分析)
- 最新的 sync_incremental_*.txt (1個最新的)
```

**📦 移至 ARCHIVE/logs/ (5個)**:
```
- 舊的 sync_incremental_*.txt 檔案
- CSV 資料檔案 cne_wj2_nbu_e5_*.csv
```

#### 4. **根目錄檔案** - 測試和臨時檔案

**🔧 保留核心檔案**:
```
- README.md
- REBUILD_GUIDE.md
- package.json, package-lock.json
- test_clickhouse_connection.py
- check_existing_tables.py
```

**📦 移至 ARCHIVE/ (5個)**:
```
- REFACTOR_REPORT.md
- REORGANIZATION_SUMMARY.md
- MSSQL_CLICKHOUSE_RECONCILIATION_SUCCESS.md
- TODO_DATA_VALIDATION.md
```

### 📊 整理統計

| 資料夾 | 目前檔案數 | 保留 | 移至 ARCHIVE | 清理比例 |
|--------|------------|------|--------------|----------|
| scripts/ | 95 | 15 | 80 | 84% |
| sql/ | 40+ | 8 | 30+ | 75% |
| logs/ | 8 | 3 | 5 | 63% |
| 根目錄 | 10 | 5 | 5 | 50% |
| **總計** | **153+** | **31** | **120+** | **78%** |

## 整理後的目標架構

```
dmp_flowable/
├── clickhouse/          # ClickHouse 核心 (已整理)
├── cube/               # Cube.js 資料模型
├── docs/               # 核心文件
├── scripts/            # 15個核心腳本
├── sql/                # 8個核心 SQL
├── logs/               # 3個重要日誌
├── sync/               # 同步腳本 (保留)
├── validation_results/ # 驗證結果 (保留)
├── docker/             # Docker 配置 (保留)
├── ARCHIVE/            # 歷史檔案 (擴充)
│   ├── scripts/        # +80個舊腳本
│   ├── sql/            # +30個舊SQL
│   ├── logs/           # +5個舊日誌
│   └── misc/           # +5個根目錄檔案
└── [核心檔案]          # 5個根目錄核心檔案
```

## 建議執行步驟

1. **確認核心腳本清單** - 確保15個核心腳本涵蓋所有必要功能
2. **確認核心SQL清單** - 確保8個核心SQL涵蓋所有業務邏輯
3. **執行批次移動** - 將120+個檔案移至對應ARCHIVE子資料夾
4. **驗證功能完整性** - 確認核心功能不受影響
5. **更新文件** - 更新README和REBUILD_GUIDE

## 風險評估

- **低風險**: 所有核心功能檔案都會保留
- **可復原**: 所有檔案移至ARCHIVE，可隨時復原
- **測試建議**: 整理後執行一次完整的重建驗證

---

**準備執行**: 請確認此分析後，我將開始執行資料夾整理作業。