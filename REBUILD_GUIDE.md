# ClickHouse → Cube.js → Superset 重建指南

**版本**: 1.0  
**更新日期**: 2026-01-26  
**適用範圍**: 從零重建完整資料管道

---

## 🎯 重建目標

建立完整的 **ClickHouse → Cube.js → Superset** 資料管道，支援 L5 任務完成率儀表板。

### 核心功能
- ✅ VARINST 優先，MDM 補齊的維度邏輯
- ✅ ISO Week 時間合規性
- ✅ MSSQL vs ClickHouse 100% 一致性
- ✅ V1/V3 歸屬邏輯 (315% 工單規則)
- ✅ 完整的 Bronze → Silver → Gold 資料流

---

## 📋 重建步驟

### Phase 1: ClickHouse 資料層重建

#### 1.1 執行 DDL 套件
```bash
# 按順序執行 DDL 腳本
clickhouse-client < clickhouse/ddl/00_databases.sql
clickhouse-client < clickhouse/ddl/10_bronze_sources.sql
clickhouse-client < clickhouse/ddl/20_silver_views_and_mviews.sql
clickhouse-client < clickhouse/ddl/30_gold_views_and_mviews.sql
clickhouse-client < clickhouse/ddl/40_validation_queries.sql
```

#### 1.2 執行驗收測試
```bash
clickhouse-client < clickhouse/ddl/validation_acceptance_test.sql
```

#### 1.3 驗證資料管道
```bash
python clickhouse/scripts/verify_mview_pipeline_completion.py
python clickhouse/scripts/verify_mssql_clickhouse_reconciliation.py
python clickhouse/scripts/execute_end_to_end_pipeline.py
```

### Phase 2: Cube.js 語意層重建

#### 2.1 啟動 Cube.js 服務
```bash
cd cube
docker-compose up -d
```

#### 2.2 驗證資料模型
- 檢查 `cube_gold_l5_task_completion.js` 載入
- 檢查 `cube_l5_dashboard_summary.js` 載入
- 測試資料存取和預聚合

#### 2.3 測試指標計算
- 驗證 L5 任務完成率計算
- 驗證維度篩選功能
- 驗證時間區間邏輯

### Phase 3: Superset 視覺化層重建

#### 3.1 連接資料源
- 配置 Cube.js 連接
- 測試資料存取

#### 3.2 建立儀表板
- 建立 L5 任務完成率儀表板
- 配置篩選器 (Vx, Plant, Factory, Line)
- 配置時間維度 (W-pattern, Dn-1)

#### 3.3 功能驗證
- 測試所有圖表和篩選
- 驗證資料準確性
- 測試效能表現

---

## ✅ 驗證清單

### ClickHouse 層驗證
- [ ] Bronze 層：原始資料表建立完成
- [ ] Silver 層：MVIEW 建立完成，維度補齊運作正常
- [ ] Gold 層：業務彙總表建立完成
- [ ] 驗證：CNE-WJ2-NBU-E5 測試案例通過
- [ ] 對帳：MSSQL vs ClickHouse 100% 一致

### Cube.js 層驗證
- [ ] 服務：Cube.js 容器正常運行
- [ ] 模型：L5 相關資料模型載入成功
- [ ] 資料：可正常存取 Gold 層資料
- [ ] 預聚合：預聚合功能正常運作
- [ ] API：GraphQL/REST API 回應正常

### Superset 層驗證
- [ ] 連接：成功連接 Cube.js 資料源
- [ ] 儀表板：L5 儀表板建立完成
- [ ] 篩選：所有篩選器功能正常
- [ ] 圖表：所有圖表顯示正確
- [ ] 效能：查詢回應時間合理

### 端到端驗證
- [ ] 資料流：Bronze → Silver → Gold → Cube.js → Superset
- [ ] 一致性：各層資料完全一致
- [ ] 功能性：所有業務需求滿足
- [ ] 效能：整體系統效能合理
- [ ] 穩定性：系統運行穩定

---

## 🔧 核心檔案說明

### ClickHouse DDL 套件
```
clickhouse/ddl/00_databases.sql              # 資料庫建立
clickhouse/ddl/10_bronze_sources.sql         # Bronze 層表格定義
clickhouse/ddl/20_silver_views_and_mviews.sql # Silver 層 MVIEW (維度補齊)
clickhouse/ddl/30_gold_views_and_mviews.sql  # Gold 層表格 (業務彙總)
clickhouse/ddl/40_validation_queries.sql     # 驗證查詢
clickhouse/ddl/validation_acceptance_test.sql # 驗收測試
```

### 核心驗證腳本
```
clickhouse/scripts/verify_mssql_clickhouse_reconciliation.py  # MSSQL-ClickHouse 對帳
clickhouse/scripts/verify_mview_pipeline_completion.py        # MVIEW 管道驗證
clickhouse/scripts/execute_end_to_end_pipeline.py            # 端到端管道執行
```

### Cube.js 資料模型
```
cube/model/cubes/cube_gold_l5_task_completion.js  # L5 任務完成率模型
cube/model/cubes/cube_l5_dashboard_summary.js     # L5 儀表板摘要模型
```

### 核心文檔
```
docs/metric_definitions.md                        # 指標定義 (v1.4)
docs/varinst_to_mdm_mapping_specification.md     # 維度映射規格
docs/ARCHITECTURE_OVERVIEW.md                    # 架構總覽
```

---

## 🚨 重要注意事項

### 資料依賴
- **Bronze 層**：依賴 MSSQL 資料同步
- **Silver 層**：依賴 Bronze 層表格和 MDM 主檔
- **Gold 層**：依賴 Silver 層 MVIEW
- **Cube.js**：依賴 Gold 層表格

### 執行順序
1. **必須按 DDL 編號順序執行** (00 → 10 → 20 → 30 → 40)
2. **驗證每個階段完成後再進行下一階段**
3. **出現錯誤時停止並排除問題**

### 效能考量
- **MVIEW 更新**：Silver 層 MVIEW 可能需要較長時間更新
- **資料量**：Gold 層表格資料量較大，查詢需要時間
- **預聚合**：Cube.js 預聚合可提升查詢效能

### 故障排除
- **DDL 執行失敗**：檢查依賴表格是否存在
- **MVIEW 更新失敗**：檢查來源資料完整性
- **對帳不一致**：檢查時間邏輯和 V1/V3 歸屬規則
- **Cube.js 連接失敗**：檢查 ClickHouse 連接配置

---

## 📞 支援資源

### 歷史記錄
- `ARCHIVE/memory/project_progress_2026_01_26.md` - 最新進度記錄
- `MSSQL_CLICKHOUSE_RECONCILIATION_SUCCESS.md` - 對帳成功記錄

### 技術分析
- `ARCHIVE/analysis/` - 詳細技術分析報告
- `ARCHIVE/validation/` - 驗證結果和測試案例
- `ARCHIVE/legacy/` - 舊版檔案和歷史實作

### 開發記錄
- `ARCHIVE/development/` - 開發過程和調試腳本

---

**重建指南版本**: 1.0  
**最後更新**: 2026-01-26  
**狀態**: 準備執行重建