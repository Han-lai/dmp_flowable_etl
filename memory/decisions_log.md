# Decisions Log

## 用途
記錄已做的技術決策與原因，避免重複討論。

## 何時更新
- 做出技術選擇時
- 改變先前決策時

## ❌ 不該寫的內容
- 待討論的選項
- 未來可能的改進
- 比較分析

---

## 決策紀錄

### 2024-12-12: 同步方案選擇

**決策**：使用 ClickHouse JDBC Bridge

**原因**：
- ClickHouse 原生支援
- 不需要額外 Python 程式
- 官方推薦方案

**放棄選項**：
- Python pyodbc（需自行維護程式）
- ODBC Table Function（Linux ODBC 設定複雜）

---

### 2024-12-12: Table Engine 選擇

**決策**：
- 歷史表使用 ReplacingMergeTree
- 設定表使用 MergeTree

**原因**：
- ReplacingMergeTree 可處理重複資料
- 增量同步時自動去重

---

### 2024-12-12: 同步策略

**決策**：
- 大表（ACT_HI_*, FlowableTaskStats）：Incremental Load
- 小表（設定表）：Full Load

**原因**：
- 大表全量同步耗時
- 小表全量同步簡單可靠

---

### 2024-12-12: MSSQL Mock Schema

**決策**：使用完整 schema（與真實系統一致）

**原因**：
- 方便測試與驗證
- 避免欄位不一致問題

**表數量**：
- APP_SRV_BPM：5 張表（21-28 欄）
- APP_SRV_COMMON：11 張表（4-52 欄）

---

### 2024-12-12: ClickHouse 連線設定

**決策**：手動建立 listen.xml 設定 `0.0.0.0`

**原因**：
- 預設只監聯 localhost
- 需要外部連線存取

---

### 2024-12-17: JDBC Bridge MSSQL 連線成功

**決策**：使用單一 `mssql_master` datasource 連線到 master database

**原因**：
- 可透過 `APP_SRV_BPM.dbo.表名` 和 `APP_SRV_COMMON.dbo.表名` 存取不同資料庫
- 簡化 datasource 管理

**關鍵設定**：
- 必須加上 `driverClassName: com.microsoft.sqlserver.jdbc.SQLServerDriver`
- 使用 JDBC Driver 7.4.1.jre8（較新版本 12.x 連線失敗）
- 使用 IP `10.136.158.140` 而非 hostname（container 內 DNS 解析問題）

**放棄選項**：
- 分開建立 `mssql_bpm` 和 `mssql_common`（不需要）
- 使用 JDBC Driver 12.x（連線失敗）
- 使用 hostname `twtpesqldv2.delta.corp`（DNS 解析不穩定）

---

### 2024-12-17: 新增 PostgreSQL 連線

**決策**：新增 `postgres_cleaned_data` datasource

**連線資訊**：
- Host: `10.136.218.208:5505`
- Database: `cleaned_data_db`

**用途**：未來可能需要從 PostgreSQL 同步資料

---

### 2024-12-18: 第一階段同步完成

**成果**：
- 16 張表全量同步完成
- 總筆數：2,134,433 筆
- 同步時間：1 分 5 秒
- 平均速度：32,837 筆/秒

---

### 2024-12-18: JDBC Bridge vs Airbyte 方案比較

**決策**：建議採用「混合式方案」

**比較結果**：
| 項目 | JDBC Bridge | Airbyte |
|------|-------------|---------|
| 同步時間 | 1 分 5 秒 | 8 分 18 秒 |
| 儲存空間 | ~137 MB | ~195 MB |
| 增量同步 | 需自行開發 | 內建支援 |
| UI 管理 | 無 | 有 |

**建議**：
- 大表（歷史表、成長快速表）：Airbyte + 增量同步
- 小表或需頻繁全量刷新表：JDBC Bridge

**原因**：
- JDBC Bridge 效能優異（7.7 倍速度）
- Airbyte 提供穩定維運與增量能力
- 依表特性選擇最適方案


---

### 2024-12-23: Silver Layer View 設計

**決策**：建立四張 Silver View

**View 結構**：
- `V_PROC_VARIABLES_PIVOTED` - 流程變數樞紐化 (Grain: PROC_INST_ID)
- `V_HI_PROC_TASK_NODE` - 任務節點層 (Grain: Task ID)
- `V_HI_PROCINST_NODE` - 流程實例層 (Grain: PROC_INST_ID)
- `V_HI_BIZ_EVENT_INFO` - 業務事件層 (Grain: BUSINESS_KEY)

**原因**：
- 對應三個分析層級：任務 → 流程 → 業務事件
- 預先計算派生欄位 (時長、狀態)
- 簡化指標查詢

---

### 2024-12-23: 流程變數樞紐化

**決策**：建立 `V_PROC_VARIABLES_PIVOTED` View

**欄位**：
- PLANT, FACTORY, REGION, SAP_PLANT, LINE_NAME, MODEL_NAME

**原因**：
- 將 varinst 的行轉列
- 其他 View 可直接 JOIN 取得變數
- 避免每次查詢都要 JOIN varinst

---

### 2024-12-23: TASK_STATUS 判斷邏輯

**決策**：採用參考環境 (flowable_analytics) 的判斷邏輯

**狀態定義**：
- CANCELLED: DELETE_REASON 不為空
- TODO: 沒有 ASSIGNEE 且沒有 END_TIME
- DOING: 有 ASSIGNEE 且沒有 END_TIME
- DONE_AUTO: 有 ASSIGNEE、沒有 CLAIM_TIME、有 END_TIME
- DONE: 有 END_TIME (其他情況)

**原因**：
- 與參考環境一致
- DONE_AUTO 定義明確：任務被指派但沒被認領就直接完成

---

### 2024-12-23: 逾期判斷邏輯

**決策**：暫緩實作

**原因**：
- 缺少 HealthSettings 表（定義紅燈天數門檻）
- 參考環境 (flowable_analytics) 也沒有此表
- 逾期判斷可能在應用層處理

---

### 2024-12-24: Scripts 目錄整理

**決策**：整理 scripts 目錄，保留 18 個正式工具，歸檔 14 個

**保留原則**：
- 現階段仍會用於指標驗證、View/RMV 對帳、Benchmark 比對
- 具備清楚用途和可重複使用性

**歸檔原則**：
- 早期 POC/探索腳本
- 一次性驗證工具
- Mock 環境相關

**刪除原則**：
- 功能已被新 script 取代
- 已整合到其他腳本
- Hard code 參數、無泛用性

---

### 2024-12-24: 邏輯等價性驗證完成

**結論**：三個環境 (Benchmark / View / RMV) 在計算邏輯上等價

**驗證方式**：
- 欄位語意對應分析
- 狀態值對應分析
- 聚合層級比較
- Join 語意比較

**筆數差異原因**：資料同步時間點不同 (Benchmark 停在 12/10，我的環境同步到 12/24)


---

### 2024-12-24: Refreshable Materialized View (RMV) 架構

**決策**：建立 4 張 RMV 作為 View 的替代方案

**RMV 清單**：
- `RMV_PROC_VARIABLES_PIVOTED` - 12,922 筆
- `RMV_HI_PROC_TASK_NODE` - 48,034 筆
- `RMV_HI_PROCINST_NODE` - 16,075 筆
- `RMV_HI_BIZ_EVENT_INFO` - 3,349 筆

**刷新頻率**：每天 02:00

**效能比較**：
- RMV 查詢速度比 View 快 4-10 倍
- RMV 總佔用空間：6.57 MiB

**資料正確性**：
- 所有 9 個指標與 View 完全一致 ✅

**原因**：
- View 每次查詢都要即時計算，效能較差
- RMV 預先計算並儲存結果，查詢速度快
- 適合報表類查詢場景

**技術要求**：
- ClickHouse 24.3+
- 需啟用 `allow_experimental_refreshable_materialized_view = 1`
- 需設定 `allow_nullable_key = 1`
