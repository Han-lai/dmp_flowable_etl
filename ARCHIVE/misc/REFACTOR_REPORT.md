# Repository Refactor Report

## 重構日期
2026-01-22

## 重構目標
整理並重構整體資料夾結構，分類為保留、封存、移除三類。

## 重構結果

### 🟢 保留 (Active/Useful): 327 個檔案
符合以下條件的檔案：
- 實際被系統使用中
- 被 Airflow / Script / SQL / Cube.js 引用
- 是正式文件或規格
- 是未來明確會使用的模組

**核心系統檔案：**
- `cube/model/cubes/cube_gold_l5_task_completion.js` - L5 任務完成率 Cube
- `cube/model/cubes/cube_gold_user_utilization.js` - 人員使用率 Cube
- `sql/00_execute_all_mviews.sql` - MView 主執行檔案
- `sql/11_create_silver_mviews_layer1.sql` - Silver 層 MView Layer 1
- `sql/12_create_silver_mviews_layer2.sql` - Silver 層 MView Layer 2
- `sql/13_create_gold_mviews.sql` - Gold 層 MView
- `docs/metric_definitions.md` - 指標定義文件

### 🟡 封存 (Archive): 14 個檔案
符合以下條件的檔案：
- 曾用於 POC、測試或舊方案
- 目前未被引用，但有保留價值
- 已移至 ARCHIVE 資料夾

**封存位置：**
- `ARCHIVE/cube/disabled/` - 停用的 Cube 檔案 (6 個)
- `ARCHIVE/docs/historical/` - 歷史文件 (8 個)

**停用的 Cube 檔案：**
- `cube_biz_event_info.js.disabled`
- `cube_daily_biz_event_snapshot.js.disabled`
- `cube_daily_metrics_snapshot.js.disabled`
- `cube_proc_inst_node.js.disabled`
- `cube_proc_task_node.js.disabled`
- `cube_vteam_region_plant_factory_line_tree.js.disabled`

### 🔴 移除 (Removable): 21 個檔案
符合以下條件的檔案：
- 純測試用、臨時檔案
- 重複檔案
- 無任何引用或歷史價值
- 可安全刪除，不影響系統運作

**已移除的檔案類型：**
- 備份 SQL 檔案 (18 個)
- 臨時 Markdown 檔案 (3 個)

## 重構後的目錄結構

```
dmp_flowable/
├── ARCHIVE/                    # 封存區
│   ├── cube/disabled/         # 停用的 Cube 檔案
│   ├── docs/historical/       # 歷史文件
│   ├── docs/                  # 舊文件
│   ├── logs/                  # 舊日誌
│   ├── memory/                # 舊記憶檔案
│   ├── misc/                  # 雜項檔案
│   ├── scripts/               # 舊腳本
│   ├── specs/                 # 舊規格
│   ├── transform/             # 舊轉換腳本
│   └── validation/            # 舊驗證腳本
├── cube/                      # Cube.js 配置
│   ├── model/cubes/          # 活躍 Cube (2 個)
│   └── model/views/          # Cube Views
├── docker/                    # Docker 配置
├── docs/                      # 活躍文件
├── logs/                      # 當前日誌
├── scripts/                   # 活躍腳本
├── sql/                       # SQL 檔案
├── sync/                      # 同步腳本
└── README.md                  # 專案說明
```

## 系統狀態確認

### ✅ 核心系統正常運作
- L5 Task Completion Cube: 正常
- User Utilization Cube: 正常
- Gold 層 MView: 支援歷史日期
- Silver 層 MView: 資料一致性驗證通過

### ✅ 資料流完整性
- Silver Fact → Silver Metrics → Gold MView: 一致
- Gold MView → L5 Cube: 一致
- Silver Tables → User Utilization Cube: 正常

### ✅ 測試案例驗證
- WJ2+NBU+E5 2025-12-30: 7 個任務 (6 TODO, 1 DOING, 0 DONE)
- 完成率: 0.0%, 執行率: 14.3%
- 所有層級數據完全一致

## 後續維護建議

1. **定期清理**: 每季度檢查 ARCHIVE 目錄，移除過時檔案
2. **文件管理**: 新增的歷史文件應直接放入 ARCHIVE/docs/historical/
3. **Cube 管理**: 停用的 Cube 檔案應加上 .disabled 後綴並移至 ARCHIVE/cube/disabled/
4. **腳本管理**: 一次性使用的腳本應在使用後移至 ARCHIVE/scripts/

## 重構影響評估

- ✅ 無系統功能影響
- ✅ 無資料流影響  
- ✅ 無 Cube.js 功能影響
- ✅ 專案結構更清晰
- ✅ 檔案數量減少 5.8% (21/362)
