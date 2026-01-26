# DMP Flowable 流程分析系統

基於 ClickHouse → Cube.js → Superset 的完整資料管道，專注於 L5 任務完成率分析。

## 🏗️ 系統架構

```
ClickHouse (資料層)
├── Bronze: 原始資料 (MSSQL 同步)
├── Silver: 維度補齊 + 清理 (MVIEW)
└── Gold: 業務彙總 (Table/View)
    ↓
Cube.js (語意層)
├── 資料模型定義
└── 預聚合配置
    ↓
Superset (視覺化層)
├── L5 儀表板
└── 圖表配置
```

## 🚀 快速重建

**完整重建指南**: 請參考 `REBUILD_GUIDE.md`

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

## 📁 檔案結構

```
├── clickhouse/           # ClickHouse 核心
│   ├── ddl/              # DDL 腳本 (00→10→20→30→40)
│   └── scripts/          # 核心驗證腳本
├── cube/                 # Cube.js 語意層
│   └── model/cubes/      # L5 資料模型
├── docker/               # 基礎設施配置
├── docs/                 # 核心文檔
└── ARCHIVE/              # 歷史記錄和分析
```

## 📊 重要文檔

- `REBUILD_GUIDE.md` - 完整重建指南
- `docs/metric_definitions.md` - 指標定義 (v1.4)
- `docs/varinst_to_mdm_mapping_specification.md` - 維度映射規格
- `ARCHIVE/memory/project_progress_2026_01_26.md` - 最新進度記錄

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

---

**Last Updated**: 2026-01-26  
**Status**: 準備生產部署