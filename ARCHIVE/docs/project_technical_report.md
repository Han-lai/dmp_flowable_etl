# DMP Flowable 資料平台技術報告

> 版本：1.0  
> 日期：2026-01-12  
> 狀態：已落地運行

---

## 一、專案背景與目標

### 1.1 為什麼需要這個專案？

DMP (Digital Manufacturing Platform) 使用 Flowable BPM 引擎管理製造流程。原始資料存放在 MSSQL，但存在以下問題：

1. **資料分散**：流程資料 (APP_SRV_BPM) 與人員資料 (APP_SRV_COMMON) 分散在不同資料庫
2. **查詢效能不足**：MSSQL 不適合大量聚合分析查詢
3. **無法回溯歷史**：只有當下狀態，無法查詢「上週的在途任務數」
4. **指標定義不一致**：各系統對「自動完成率」等指標的計算方式不同

### 1.2 專案要解決的核心問題

| 問題 | 解決方案 |
|------|----------|
| 資料分散 | 統一同步到 ClickHouse |
| 查詢效能 | 使用 RMV 預計算，查詢快 4-10 倍 |
| 無法回溯 | 建立 Gold 每日快照，保留 365 天 |
| 指標不一致 | 透過 Cube.js 語意層統一定義 |

### 1.3 為什麼選擇 Bronze / Silver / Gold 分層？

這是資料倉儲的標準分層模型，各層職責明確：

| 層級 | 職責 | 特性 |
|------|------|------|
| **Bronze** | 原始資料落地 | 不做轉換，可重跑，保留完整歷史 |
| **Silver** | 清洗、JOIN、初步彙總 | 建立分析用的寬表，派生欄位 |
| **Gold** | 業務指標、歷史快照 | 可直接用於報表，支援回溯 |

**選擇原因**：
- 職責分離，問題容易定位
- 每層可獨立重跑，不影響其他層
- 符合業界標準，團隊容易理解

---

## 二、整體架構總覽

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MSSQL (Source)                                 │
│                                                                             │
│   APP_SRV_BPM (5 表)              APP_SRV_COMMON (11 表)                    │
│   ├── ACT_HI_PROCINST             ├── HR_Employee                          │
│   ├── ACT_HI_TASKINST             ├── ProcessRoleUserMapping               │
│   ├── ACT_HI_VARINST              └── ... (9 張設定表)                      │
│   ├── ACT_HI_IDENTITYLINK                                                   │
│   └── ACT_RE_PROCDEF                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ JDBC Bridge (ClickHouse 內建)
                                      │ sync/sync_incremental.py
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Bronze Layer (ClickHouse)                         │
│                                                                             │
│   16 張表 (ReplacingMergeTree / MergeTree)                                  │
│   ├── 大表 (5 張): 增量同步，Watermark 追蹤                                  │
│   └── 小表 (11 張): 全量同步，DROP + CREATE                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
┌───────────────────────────────┐   ┌───────────────────────────────────────┐
│   Silver View (即時查詢)       │   │   Silver RMV (效能優先)                │
│                               │   │                                       │
│   V_PROC_VARIABLES_PIVOTED    │   │   RMV_PROC_VARIABLES_PIVOTED          │
│   V_HI_PROC_TASK_NODE         │   │   RMV_HI_PROC_TASK_NODE               │
│   V_HI_PROCINST_NODE          │   │   RMV_HI_PROCINST_NODE                │
│   V_HI_BIZ_EVENT_INFO         │   │   RMV_HI_BIZ_EVENT_INFO               │
│                               │   │                                       │
│   (每次查詢即時計算)           │   │   (每日 02:00 UTC 自動刷新)            │
└───────────────────────────────┘   └───────────────────────────────────────┘
                                                        │
                                                        ▼
                                    ┌───────────────────────────────────────┐
                                    │   Gold Layer (每日快照)                │
                                    │                                       │
                                    │   gold.DAILY_METRICS_SNAPSHOT         │
                                    │   gold.DAILY_BIZ_EVENT_SNAPSHOT       │
                                    │                                       │
                                    │   (每日 10:00 Asia/Taipei 快照)        │
                                    └───────────────────────────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Cube.js (語意層)                                   │
│                                                                             │
│   Silver Cubes:                    Gold Cubes:                              │
│   ├── ProcTaskNode                 ├── DailyMetricsSnapshot                 │
│   ├── ProcInstNode                 └── DailyBizEventSnapshot                │
│   └── BizEventInfo                                                          │
│                                                                             │
│   Views (對外 API):                                                          │
│   ├── HistoricalTrends                                                      │
│   └── HistoricalBizEvents                                                   │
│                                                                             │
│   REST API: http://localhost:4002                                           │
│   Playground: http://localhost:4003                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │   前端 / BI    │
                              └───────────────┘
```

---

## 三、資料分層設計說明

### 3.1 Bronze 層

#### 資料來源
- **MSSQL Server**：`10.136.158.140`
- **資料庫**：APP_SRV_BPM (Flowable 流程) + APP_SRV_COMMON (人員組織)
- **表數量**：16 張

#### 同步方式
- **工具**：ClickHouse JDBC Bridge
- **腳本**：`sync/sync_incremental.py`
- **策略**：混合式（大表增量 + 小表全量）

#### 為什麼 Bronze 不做轉換？

1. **可回溯**：保留原始資料，出問題可追溯
2. **可重跑**：同步失敗可重新執行，不影響下游
3. **解耦**：來源 schema 變更時，只需調整 Bronze，不影響 Silver

#### 增量 vs 全量處理

| 類型 | 表數 | 策略 | 原因 |
|------|------|------|------|
| 大表 | 5 張 | 增量 (Watermark) | 資料量大 (50K~1.3M)，全量太慢 |
| 小表 | 11 張 | 全量 (DROP+CREATE) | 資料量小 (<1K)，全量簡單可靠 |

#### 設計原則
- 使用 `ReplacingMergeTree` 處理重複資料
- 加入 `_sync_time` 欄位追蹤同步時間
- Watermark 表記錄上次同步位置

---

### 3.2 Silver 層

#### Silver 中的兩種型態

| 類型 | 數量 | 刷新方式 | 用途 |
|------|------|----------|------|
| **View** | 4 張 | 即時計算 | 需要最新資料時使用 |
| **RMV** | 4 張 | 每日自動 | 報表查詢，效能優先 |

#### 為什麼選擇 RMV？

效能比較：

| 查詢 | View (ms) | RMV (ms) | 加速比 |
|------|-----------|----------|--------|
| 在途任務總數 | 147 | 15 | **10.1x** |
| TASK_STATUS 分布 | 123 | 14 | **9.1x** |
| 自動完成率 | 95 | 11 | **8.6x** |

RMV 預計算結果，查詢時直接讀取，不需要每次 JOIN。

#### Silver 負責的事情

1. **清洗**：處理 NULL、格式轉換
2. **JOIN**：將分散的表關聯起來
3. **派生欄位**：計算 TASK_STATUS、時長等
4. **樞紐化**：將 EAV 格式轉為寬表

#### 為什麼 Silver 不直接當 Gold？

Silver 是「分析素材」，不是「業務指標」：
- Silver 提供明細資料，可切任意維度
- Gold 是固定維度的聚合結果，支援歷史回溯
- Silver 無法回答「上週的在途任務數是多少」

---

### 3.3 Gold 層

#### 為什麼一開始沒有做 Physical Gold？

1. **需求不明確**：初期只需要即時查詢
2. **避免過度設計**：先用 Silver + Cube.js 驗證需求
3. **漸進式演進**：確認需要歷史趨勢後才補建

#### 什麼需求出現後決定補 Gold？

用戶提出：
- 「我想看本週 vs 上週的在途任務數變化」
- 「我需要每月報表，回溯過去一年的指標」

這些需求 Silver 無法滿足，因為 Silver 只有「當下狀態」。

#### Gold 是 snapshot 型

- **類型**：Daily Snapshot（每日快照）
- **不是** Event 型（不記錄每筆變更）

#### 設計決策

| 項目 | 決策 | 原因 |
|------|------|------|
| 快照時間 | 10:00 Asia/Taipei | 業務上班時間，資料較穩定 |
| 保留期限 | 365 天 | 支援年度報表 |
| 維度 | factory, plant, proc_def_name | 最常用的分析維度 |
| 表引擎 | ReplacingMergeTree | 支援重跑去重 |

---

## 四、同步與刷新策略

### 4.1 策略總覽

| 層級 | 同步方式 | 觸發方式 | 可否重跑 | 設計理由 |
|------|----------|----------|----------|----------|
| Bronze (大表) | Incremental | 手動 | ✅ 可 | 資料量大，全量太慢 |
| Bronze (小表) | Full Refresh | 手動 | ✅ 可 | 資料量小，全量簡單 |
| Silver View | 即時計算 | On-query | N/A | 需要最新資料 |
| Silver RMV | Full Refresh | 每日自動 | ✅ 可 | 效能優先 |
| Gold | Daily Snapshot | 手動 | ✅ 可 | 歷史趨勢 |

### 4.2 為什麼不能全部用 Incremental？

1. **小表沒必要**：資料量小，全量更簡單
2. **無追蹤欄位**：部分表沒有 LAST_UPDATED_TIME
3. **DELETE 無法追蹤**：增量同步無法捕捉刪除

### 4.3 回補與重跑策略

| 場景 | 策略 |
|------|------|
| Bronze 同步失敗 | 重新執行 `sync_incremental.py`，ReplacingMergeTree 自動去重 |
| RMV 刷新失敗 | 手動執行 `SYSTEM REFRESH VIEW` |
| Gold 快照遺漏 | 執行 `create_gold_snapshot.py --date YYYY-MM-DD` |

### 4.4 避免重複資料

- **Bronze**：使用 `ReplacingMergeTree(_sync_time)`，相同主鍵保留最新版本
- **Gold**：使用 `ReplacingMergeTree(_version)`，同日期重跑會覆蓋

---

## 五、工具選擇與取捨

### 5.1 ClickHouse

| 項目 | 說明 |
|------|------|
| **角色** | 資料倉儲，儲存 Bronze/Silver/Gold 所有資料 |
| **為什麼選它** | 列式儲存，聚合查詢快；支援 RMV 自動刷新 |
| **負責什麼** | 資料儲存、查詢、RMV 排程 |
| **不負責什麼** | 資料抽取（由 JDBC Bridge 處理） |
| **未來調整** | 如資料量暴增，可能需要分散式部署 |

### 5.2 JDBC Bridge

| 項目 | 說明 |
|------|------|
| **角色** | 跨資料庫查詢，從 MSSQL 拉資料到 ClickHouse |
| **為什麼選它** | ClickHouse 原生支援，不需額外元件 |
| **負責什麼** | 執行 `SELECT * FROM jdbc(...)` |
| **不負責什麼** | 排程、Watermark 管理（由 Python 處理） |
| **未來調整** | 如需 CDC，可能改用 Debezium |

### 5.3 Cube.js

| 項目 | 說明 |
|------|------|
| **角色** | 語意層，統一指標定義，提供 REST API |
| **為什麼選它** | 開源、支援 ClickHouse、有 Playground |
| **負責什麼** | 指標定義、維度約束、API 封裝 |
| **不負責什麼** | 資料落地、排程、ETL |
| **未來調整** | 如需更複雜的權限控制，可能需要額外方案 |

### 5.4 排程工具（待補）

| 項目 | 說明 |
|------|------|
| **角色** | 自動執行 Bronze 同步和 Gold 快照 |
| **目前狀態** | 手動執行，尚未自動化 |
| **建議方案** | cron / Windows Task Scheduler / Airflow |
| **未來調整** | 如需複雜依賴管理，建議用 Airflow |

---

## 六、指標與查詢架構

### 6.1 指標計算位置

| 指標類型 | 計算位置 | 原因 |
|----------|----------|------|
| 即時指標 | Silver RMV + Cube.js | 需要最新資料 |
| 歷史趨勢 | Gold + Cube.js | 需要回溯 |
| 複雜聚合 | Cube.js | 語意層統一定義 |

### 6.2 為什麼不全放 Cube.js？

Cube.js 是「查詢語意層」，不是「資料儲存層」：
- Cube.js 不能執行 INSERT
- Cube.js 不能排程寫入
- 歷史快照必須落地到 Gold 表

### 6.3 avg / rate 指標的處理

**問題**：avg 和 rate 不可直接跨維度平均

```
Plant A 自動完成率: 80% (8/10)
Plant B 自動完成率: 60% (6/10)
Factory 平均: (80% + 60%) / 2 = 70% ❌ 錯誤
Factory 正確: (8+6) / (10+10) = 70% ✅
```

**解決方案**：每個 avg/rate 指標都提供分子分母

| 指標 | 分子 | 分母 |
|------|------|------|
| autoCompleteRate | doneAutoForRate | doneTotalForRate |
| avgWorkDuration | totalWorkDuration | doneCount |

---

## 七、效能與時間設計

### 7.1 同步效能

| 方式 | 耗時 | 資料量 | 吞吐量 |
|------|------|--------|--------|
| 全量同步 | ~68 秒 | 2,134,433 筆 | ~31,389 rows/sec |
| 增量同步 | ~10 秒 | 增量資料 | - |

### 7.2 查詢效能

| 查詢 | View | RMV | 加速比 |
|------|------|-----|--------|
| 在途任務總數 | 147ms | 15ms | 10.1x |
| TASK_STATUS 分布 | 123ms | 14ms | 9.1x |

### 7.3 資料新鮮度

| 層級 | 最大延遲 |
|------|----------|
| Bronze | 取決於同步頻率（目前手動） |
| Silver RMV | ≤ 24 小時 |
| Gold | ≤ 24 小時（每日快照） |

### 7.4 何時需要下沉 Gold？

當出現以下需求時：
- 需要查詢「上週/上月」的指標值
- 需要做時間序列分析
- 需要指標回溯

---

## 八、文件與程式對照表

### 8.1 SQL 檔案

| 檔案 | 角色 | 解決什麼問題 |
|------|------|--------------|
| `sql/01_create_database.sql` | 建立 bronze database | 初始化環境 |
| `sql/02_create_bpm_tables.sql` | 建立 BPM 相關表 | Bronze 表結構 |
| `sql/03_create_common_tables.sql` | 建立 Common 相關表 | Bronze 表結構 |
| `sql/04_create_silver_database.sql` | 建立 silver database | 初始化環境 |
| `sql/05_create_silver_views.sql` | 建立 Silver View | 即時查詢 |
| `sql/06_create_silver_rmv.sql` | 建立 Silver RMV | 效能優化 |
| `sql/07_create_gold_snapshot.sql` | 建立 Gold 表 | 歷史快照 |

### 8.2 同步腳本

| 檔案 | 角色 | 解決什麼問題 |
|------|------|--------------|
| `sync/sync_incremental.py` | 增量+全量混合同步 | 日常同步 |
| `sync/sync_to_clickhouse.py` | 全量同步（舊版） | 首次建立/重建 |

### 8.3 管理腳本

| 檔案 | 角色 | 解決什麼問題 |
|------|------|--------------|
| `scripts/create_gold_snapshot.py` | 建立每日快照 | 歷史趨勢 |
| `scripts/create_rmv.py` | 建立 RMV | 首次建立 |
| `scripts/check_rmv_status.py` | 檢查 RMV 狀態 | 監控 |
| `scripts/query_metrics_rmv.py` | 查詢指標 | 驗證 |

### 8.4 文件

| 檔案 | 角色 | 解決什麼問題 |
|------|------|--------------|
| `CLAUDE.md` | 專案快速上手 | 新人入門 |
| `docs/data_flow_guide.md` | 資料流程說明 | 理解架構 |
| `docs/metric_definitions.md` | 指標業務定義 | 統一口徑 |
| `docs/semantic_gold_governance.md` | 指標治理規範 | 正確使用指標 |
| `docs/current_architecture_paths.md` | 架構路徑盤點 | 理解資料流 |
| `docs/jdbc_bridge_performance_guide.md` | 效能量測指南 | 效能調優 |

### 8.5 Cube.js Model

| 檔案 | 角色 | 解決什麼問題 |
|------|------|--------------|
| `cube/model/cubes/cube_proc_task_node.js` | 任務層 Cube | 任務指標 API |
| `cube/model/cubes/cube_proc_inst_node.js` | 流程層 Cube | 流程指標 API |
| `cube/model/cubes/cube_biz_event_info.js` | 業務事件 Cube | 事件指標 API |
| `cube/model/cubes/cube_daily_metrics_snapshot.js` | Gold Cube | 歷史趨勢 API |
| `cube/model/views/view_historical_trends.js` | 歷史趨勢 View | 簡化 API |

---

## 九、目前架構的完成度與定位

### 9.1 已完成的能力

1. **資料同步**：MSSQL → ClickHouse Bronze，支援增量
2. **資料轉換**：Silver View/RMV，派生欄位、JOIN
3. **歷史快照**：Gold 每日快照，保留 365 天
4. **語意層**：Cube.js 統一指標定義，REST API
5. **效能優化**：RMV 預計算，查詢快 4-10 倍
6. **指標治理**：7 個 Gold 指標，有使用規範

### 9.2 刻意沒有做的事

| 項目 | 原因 |
|------|------|
| 自動排程 | MVP 階段，手動執行足夠 |
| CDC 即時同步 | 目前延遲可接受，不需要即時 |
| 資料品質監控 | 待生產環境再建立 |
| 權限控制 | 目前單一使用者，不需要 |

### 9.3 適用規模與情境

| 項目 | 適用範圍 |
|------|----------|
| 資料量 | 百萬級（目前 2M 筆） |
| 查詢頻率 | 中低頻（報表、Dashboard） |
| 使用者 | 內部分析人員 |
| 延遲要求 | 小時級（非即時） |

### 9.4 未來擴充方向

| 需求 | 建議方向 |
|------|----------|
| 需要即時同步 | 引入 CDC (Debezium + Kafka) |
| 資料量暴增 | ClickHouse 分散式部署 |
| 需要自動排程 | 引入 Airflow |
| 需要權限控制 | Cube.js 多租戶或 API Gateway |

---

## 附錄 A：比較與驗證文件溯源表

本章節統整專案中曾執行的比較、實驗、驗證工作，說明每份文件的來源腳本與產出關係。

### A.1 比較文件總覽

| 文件 | 角色/目的 | 來源腳本 | 比較內容 | 產出結果 |
|------|----------|----------|----------|----------|
| `docs/MSSQL_ClickHouse_比較報告.md` | JDBC Bridge vs Airbyte 方案選型 | `scripts/archive/compare_databases.py` | 筆數、儲存空間、同步時間 | JDBC Bridge 快 7.7 倍、省 30% 空間 |
| `docs/logic_equivalence_audit_report.md` | Benchmark vs View vs RMV 邏輯等價性 | `scripts/archive/logic_audit.py` | 欄位對應、狀態分布、指標計算 | 三環境邏輯等價 |
| `docs/view_rmv_semantic_analysis.md` | View vs RMV SQL 語意分析 | 手動分析 | SQL 結構、JOIN、欄位 | V_HI_BIZ_EVENT_INFO 完全等價，其他有欄位差異 |

### A.2 比較腳本對照表

| 腳本 | 位置 | 比較對象 | 產出 | 執行結果檔 |
|------|------|----------|------|------------|
| `compare_databases.py` | `scripts/archive/` | bronze (JDBC) vs default (Airbyte) | 筆數、大小、schema 差異 | `logs/compare_result_20251218_154611.txt` |
| `compare_view_rmv.py` | `scripts/` | View vs RMV | 效能 (ms)、儲存空間 | 終端輸出 |
| `compare_data_accuracy.py` | `scripts/` | View vs RMV | 9 個指標數值一致性 | 終端輸出 |
| `compare_with_benchmark.py` | `scripts/` | Benchmark vs View vs RMV | 狀態分布、指標比對 | 終端輸出 |
| `compare_17_metrics.py` | `scripts/archive/` | Benchmark vs View vs RMV | 17 個指標三環境比較 | 終端輸出 |
| `logic_audit.py` | `scripts/archive/` | Benchmark vs View vs RMV | 欄位結構、狀態語意 | 終端輸出 |
| `compare_formula.py` | `scripts/archive/` | Benchmark vs 我的環境 | TASK_STATUS 計算邏輯 | 終端輸出 |

### A.3 驗證結果摘要

| 驗證項目 | 結論 | 來源 |
|----------|------|------|
| JDBC Bridge vs Airbyte 效能 | JDBC 快 7.7 倍 | `compare_databases.py` |
| View vs RMV 資料一致性 | ✅ 完全一致 | `compare_data_accuracy.py` |
| View vs RMV 效能 | RMV 快 4-10 倍 | `compare_view_rmv.py` |
| Benchmark vs View 邏輯等價 | ✅ 等價 (欄位名不同) | `logic_audit.py` |
| TASK_STATUS 計算邏輯 | ✅ 與 Benchmark 一致 | `compare_formula.py` |

### A.4 執行結果檔案

| 檔案 | 內容 | 產生日期 |
|------|------|----------|
| `logs/compare_result_20251218_154611.txt` | JDBC vs Airbyte 比較結果 | 2025-12-18 |
| `logs/sync_result_*.txt` | 同步執行結果 | 多次 |
| `logs/sync_incremental_*.txt` | 增量同步結果 | 多次 |

---

## 附錄 B：連線資訊

| 服務 | 位址 | 用途 |
|------|------|------|
| ClickHouse | REDACTED_IP:8121 | 資料倉儲 |
| Cube.js API | localhost:4002 | REST API |
| Cube.js Playground | localhost:4003 | 查詢介面 |
| MSSQL | 10.136.158.140 | 資料來源 |

---

**文件結束**
