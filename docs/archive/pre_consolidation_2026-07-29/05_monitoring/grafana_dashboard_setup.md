# Grafana 儀表板設定指南

**最後更新**: 2026-07-02

本文件涵蓋兩個獨立的 Grafana Dashboard：

| Dashboard | 目的 | Datasource |
|---|---|---|
| [Bronze Sync Monitoring](#一-bronze-sync-monitoring-dashboard) | 監控每日 MSSQL→Bronze 同步是否成功 | ClickHouse `<CLICKHOUSE_HOST>`（正式環境） |
| [clickhouse-l5-perf](#二-l5-效能監控-dashboard) | 監控 L5 查詢對 ClickHouse 資源的消耗 | ClickHouse `<MONITOR_HOST>` + Prometheus |

Grafana 入口：`http://<MONITOR_HOST>:9003`

> 主機實際 IP 不進版控：`<CLICKHOUSE_HOST>` 見 `infra/.env`，`<MONITOR_HOST>` 見 `infra/monitoring/.env`。

---

## 一、Bronze Sync Monitoring Dashboard

**目的**：每日排程（`sync_unified_odbc.py`）同步 MSSQL→Bronze 的健康狀態監控。過去曾因 `MSSQL_PASSWORD` 環境變數缺失，導致 full 策略表在 TRUNCATE 後 INSERT 失敗、15 張維度表連續三天被清空（2026-06-17/29/30 事故）。此 Dashboard 讓異常可見。

**Dashboard uid**: `afe90588-6fc1-494e-9b97-9a4d5e2b0cf6`
**Datasource**: `grafana-clickhouse-datasource-76`（uid: `cfqkyxfkb2hhcf`），指向正式 ClickHouse `<CLICKHOUSE_HOST>:9000`

### Panel 清單

**Panel 1 — 近 24 小時失敗計數**（type: stat）
- 資料源：`system.query_log`
- 顏色閾值：0 筆 = 綠，≥1 筆 = 紅
```sql
SELECT count() AS failed_count
FROM system.query_log
WHERE type = 'ExceptionBeforeStart'
  AND query ILIKE '%bronze.%'
  AND event_time >= now() - INTERVAL 1 DAY
```

**Panel 2 — 失敗清單**（type: table）
- 資料源：`system.query_log`
- 顯示欄位：`event_time`、`query_kind`、`short_query`、`exception`（前 300 字）
```sql
SELECT event_time AS time, query_kind,
       substring(query, 1, 150) AS short_query,
       substring(exception, 1, 300) AS exception
FROM system.query_log
WHERE type = 'ExceptionBeforeStart'
  AND query ILIKE '%bronze.%'
  AND event_time >= now() - INTERVAL 7 DAY
ORDER BY event_time DESC LIMIT 200
```

**Panel 3 — 失敗次數趨勢（7 天，每小時）**（type: timeseries）
```sql
SELECT toStartOfHour(event_time) AS time, count() AS failed_count
FROM system.query_log
WHERE type = 'ExceptionBeforeStart'
  AND query ILIKE '%bronze.%'
  AND event_time >= now() - INTERVAL 7 DAY
GROUP BY time ORDER BY time
```

**Panel 4 — 表狀態總覽**（type: table，最重要）
- 結合 `bronze._sync_watermark`（最後成功時間，快速查詢）+ `system.query_log`（最後失敗時間）
- **判斷邏輯依 `sync_tables.yaml` 的 strategy 分流**：
  - `full` 策略（15 張，有 TRUNCATE）：`current_rows = 0` → 🔴 空表 (TRUNCATE後寫入失敗)
  - `batch` 策略（4 張，無 TRUNCATE）：不看 `current_rows`，只看 `hours_since_success >= 24` → 🟠 過期未更新
  - 兩者都正常 → ✅ 正常

| status 值 | 顏色 | 觸發條件 |
|---|---|---|
| 🔴 空表 (TRUNCATE後寫入失敗) | 紅 | full 表 `current_rows = 0` |
| 🟠 過期未更新 (逾24小時未成功) | 橘 | `hours_since_success >= 24` |
| ✅ 正常 | 綠 | 以上皆不符合 |

> **診斷方法**：看到 🔴 後，前往 Panel 2 找對應表名的 `exception` 欄位，確認是「密碼問題（`Login failed`）」還是「DSN 問題（`Data source name not found`）」，根因不同修復方式也不同。

---

## 二、L5 效能監控 Dashboard

這份設定專為 **L5 指標 (任務完成率)** 效能分析設計。核心目的是監控 L5 查詢（包含 MView 刷新與報表讀取）對 ClickHouse 資源的實際消耗。

---

## Dashboard 佈局藍圖 (Layout Map)

建議採用 Grafana 的 12 欄 (Column) 網格系統排版，讓效能診斷具有故事連續性：

```text
+---------------------------------------------------------------------------------------+
| Row 1: M (系統大盤 - 確認主機穩不穩定)                                         |
+---------acro Health-------------+----------------------+-----------------------------------------+
| [1.1] CPU Load %     | [1.2] Mem Avail %    | [3.1] Background Tasks                  |
| (Type: Gauge)        | (Type: Gauge)        | (Type: Time series)                     |
| (Width: 4)           | (Width: 4)           | (Width: 4)                              |
+----------------------+----------------------+-----------------------------------------+

+---------------------------------------------------------------------------------------+
| Row 2: L5 Query Impact (效能核心 - 觀測 L5 查詢對硬體的真實佔用)                           |
+-------------------------------------------+-------------------------------------------+
| [2.1] CPU Consumption (CH vs Sys)         | [2.2] Memory Allocation (OS vs Internal)  |
| (Type: Time series)                       | (Type: Time series)                       |
| (Width: 6)                                | (Width: 6)                                |
+-------------------------------------------+-------------------------------------------+

+---------------------------------------------------------------------------------------+
| Row 3: Deep Dive & Activity (深度剖析 - 捕捉瞬時尖峰與查詢明細)                              |
+----------------------+----------------------+-----------------------------------------+
| [2.3] Disk I/O Rates | [3.2] Mem Peaks      | [3.3] Expensive Queries                 |
| (Type: Time series)  | (Type: Time series)  | (Type: Table)                           |
| (Width: 4)           | (Width: 4)           | (Width: 4)                              |
+----------------------+----------------------+-----------------------------------------+
```

---

## 必備前置設定 1：建立 Dashboard 變數 (Variables)

為了能動態切換主機與確保 PromQL 正確運作，請至 `Dashboard settings` -> `Variables` 建立以下變數：

1. **變數 `job`**
   * **Name**: `job`
   * **Type**: `Query`
   * **Data source**: `Prometheus`
   * **Query**: `label_values(ClickHouseProfileEvents_OSCPUVirtualTimeMicroseconds, job)`
   * **Refresh**: `On dashboard load`

2. **變數 `node`**
   * **Name**: `node`
   * **Type**: `Query`
   * **Data source**: `Prometheus`
   * **Query**: `label_values(ClickHouseProfileEvents_OSCPUVirtualTimeMicroseconds{job=~"$job"}, instance)`
   * **Refresh**: `On time range change`
   * **Selection options**: 勾選 `Multi-value` 與 `Include All option`

---

### 2. Annotations (L5 查詢時間標記)
這是在所有圖表上畫出 L5 執行區間的關鍵。
*   **資料來源 (Data Source)**: `ClickHouse`
*   **Query**:
    ```sql
    SELECT
      query_start_time AS time,
      CASE
        WHEN query_duration_ms > 0
        THEN query_start_time + toIntervalMillisecond(query_duration_ms)
        ELSE NULL
      END AS timeEnd,
      concat('L5 Query (', toString(query_duration_ms), 'ms)') AS text,
      'l5-query' AS tags
    FROM system.query_log
    WHERE type = 'QueryFinish'
      AND (
        query ILIKE '%rmv_l5_task_completion_v2%'  -- Gold MView 刷新 & Cube.js 讀取查詢
        OR query ILIKE '%mv_fact_task_vx%'      -- Silver 層事實表 (MView 刷新時會大量讀取)
      )
      AND query NOT LIKE '%system.query_log%'  -- 排除 Annotation 自身查詢
      AND query_start_time >= $__fromTime AND query_start_time <= $__toTime
    ORDER BY query_start_time DESC
    ```

---

## 區塊一：Macro Health（系統大盤）

### Panel 1.1: System CPU Load (%)
*   **建議名稱**: System Total CPU Load (%)
*   **資料來源 (Data Source)**: `Prometheus`
*   **圖表類型**: Gauge
*   **單位**: `Percent (0.0-1.0)`
*   **查詢語法 (PromQL)**:
    ```promql
    1 - avg(rate(node_cpu_seconds_total{instance="docker-host", mode="idle", cpu=~"[0-7]"}[5m]))
    ```
    > 需加 `cpu=~"[0-7]"` 過濾 stale series（主機 8 核但 Prometheus 累積 274 筆歷史 series）。
*   **Thresholds**:
    *   Green: 0 ~ 0.7（< 70%）
    *   Yellow: 0.7 ~ 0.9（70~90%）
    *   Red: > 0.9（> 90%）

### Panel 1.2: System Memory Available (%)
*   **建議名稱**: System Memory Available (%)
*   **資料來源 (Data Source)**: `Prometheus`
*   **圖表類型**: Gauge
*   **單位**: `Percent (0.0-1.0)`
*   **查詢語法 (PromQL)**:
    ```promql
    node_memory_MemAvailable_bytes{instance="docker-host"} / node_memory_MemTotal_bytes{instance="docker-host"}
    ```
    > 輸出 0~1，例如 0.45 = 45% 可用。
*   **Thresholds**（反轉，可用率越低越危險）:
    *   Red: 0 ~ 0.1（< 10% 可用）
    *   Yellow: 0.1 ~ 0.3（10~30% 可用）
    *   Green: > 0.3（> 30% 可用）

---

## 區塊二：L5 Query Impact（查詢影響）

### Panel 2.1: CPU Utilization（ClickHouse vs 其他服務 vs 整機）
*   **建議名稱**: CPU Utilization: ClickHouse vs Others vs Host
*   **圖表類型**: Time series（Stacking: Normal，以面積圖呈現佔比）
*   **資料來源 (Data Source)**: `Prometheus`
*   **單位**: `Percent (0.0-1.0)`
*   **查詢語法 (PromQL)**:
    *   **A (ClickHouse CPU)**:
        ```promql
        rate(ClickHouseProfileEvents_OSCPUVirtualTimeMicroseconds{job=~"$job", instance=~"$node"}[5m]) / 1000000 / 8
        ```
        > Legend: `ClickHouse`
    *   **B (整機 CPU)**:
        ```promql
        1 - avg(rate(node_cpu_seconds_total{instance="docker-host", mode="idle", cpu=~"[0-7]"}[5m]))
        ```
        > Legend: `Host Total`
    *   **C (其他服務 = B − A)**:
        ```promql
        (1 - avg(rate(node_cpu_seconds_total{instance="docker-host", mode="idle", cpu=~"[0-7]"}[5m]))) - (rate(ClickHouseProfileEvents_OSCPUVirtualTimeMicroseconds{job=~"$job", instance=~"$node"}[5m]) / 1000000 / 8)
        ```
        > Legend: `Others (Cube.js/Superset/...)`
*   **Field Overrides**:
    *   A：Color: `orange`，Stack series: Normal
    *   B：Color: `blue`，Draw style: **Lines**（不堆疊，作為總量參考線）
    *   C：Color: `green`，Stack series: Normal
    > 判讀：橘色面積 = ClickHouse，綠色面積 = 其他服務，藍色線 = 整機。

> 若需查看個別容器 CPU，需啟用 `docker-compose.monitor.yml` 中的 **cAdvisor**，透過 `container_cpu_usage_seconds_total` 按容器名稱拆分。

### Panel 2.2: Memory Allocation (OS vs Internal)
*   **建議名稱**: ClickHouse Memory: Resident vs Internal (L5 Analysis)
*   **資料來源 (Data Source)**: `Prometheus`
*   **圖表類型**: Time series | **單位**: `bytes (IEC)`
*   **查詢語法 (PromQL)**:
    *   **A (OS Resident)**: `avg_over_time(ClickHouseAsyncMetrics_MemoryResident{job=~"$job", instance=~"$node"}[1m])`
    *   **B (CH Tracking)**: `clamp_min(ClickHouseMetrics_MemoryTracking{job=~"$job", instance=~"$node"}, 0)`

### Panel 2.3: Disk I/O Throughput (Read vs Write)
*   **建議名稱**: ClickHouse Disk I/O Rates (L5 Analysis)
*   **資料來源 (Data Source)**: `Prometheus`
*   **圖表類型**: Time series | **單位**: `bytes/sec (IEC)`
*   **查詢語法 (PromQL)**:
    *   **A (Read)**: `rate(ClickHouseProfileEvents_OSReadBytes{job=~"$job", instance=~"$node"}[1m])`
    *   **B (Write)**: `rate(ClickHouseProfileEvents_OSWriteBytes{job=~"$job", instance=~"$node"}[1m])`

---

## 區塊三：Engine Behavior & Deep Dive (引擎深度剖析)
**故事結尾**：資料庫背後在忙什麼？剛才是哪條 SQL 最吃資源？

### Panel 3.1: Background Tasks (Merges/Mutations)
*   **建議名稱**: ClickHouse Background Tasks (Merges)
*   **資料來源 (Data Source)**: `Prometheus`
*   **圖表類型**: Time series | **單位**: `short` (數量)
*   **查詢語法 (PromQL)**: `ClickHouseMetrics_BackgroundMergesAndMutationsPoolTask{job=~"$job"}`

**Grafana 建立步驟**：

1. Dashboard → Add Panel → Add a new panel
2. 右上角 Data Source 選 **Prometheus**
3. Query 輸入欄位切換為 **Code** 模式，貼入：
   ```
   ClickHouseMetrics_BackgroundMergesAndMutationsPoolTask{job=~"$job"}
   ```
4. 右側面板設定：
   - Title：`ClickHouse Background Tasks (Merges)`
   - Visualization：選 **Time series**
   - Standard options → Unit：搜尋 `short`（純數值）
   - Standard options → Min：`0`
5. Graph styles：
   - Style：**Lines**
   - Line width：`2`
   - Fill opacity：`10`
6. Thresholds：
   - Add threshold → 值 `20`，顏色 `Yellow`
   - Add threshold → 值 `50`，顏色 `Red`
7. 點選 **Apply** 儲存

> 此指標來自 ClickHouse 透過 Prometheus Exporter 暴露的 Metrics，反映 MergeTree 引擎正在執行的 Background Merge 與 Mutation 任務數量。正常值為個位數，超過 20 表示合併堆積。

### Panel 3.2: Query Memory Peaks (High Fidelity)
*   **建議名稱**: L5 Analysis: Memory Peaks (from Logs)
*   **資料來源 (Data Source)**: `ClickHouse`
*   **圖表類型**: Time series (切換為 **Points** 或 **Bars** 顯示最直觀)
*   **單位**: `bytes (IEC)`
*   **查詢語法 (SQL)**:
    ```sql
    SELECT
        query_start_time AS time,
        memory_usage AS "Peak RAM Usage"
    FROM system.query_log
    WHERE type = 'QueryFinish'
      AND (query ILIKE '%rmv_l5_task_completion_v2%' OR query ILIKE '%mv_fact_task_vx%')
      AND query_start_time >= $__fromTime AND query_start_time <= $__toTime
      AND query NOT LIKE '%system.query_log%'
    ORDER BY query_start_time
    ```
*   **說明**: **[必推]** 這個面板直接讀取日誌，能捕捉到 Prometheus (15s 一次) 漏掉的所有短暫高峰。

### Panel 3.3: Latest L5 Query
*   **建議名稱**: Latest L5 Query
*   **資料來源 (Data Source)**: `ClickHouse`
*   **圖表類型**: Table (表格)
*   **查詢語法 (SQL)**:
    ```sql
    SELECT
        query_start_time AS time,
        query_duration_ms / 1000 AS "Duration (sec)",
        CASE
            WHEN http_user_agent LIKE '%clickhouse-js%' THEN 'Cube.js (Superset)'
            WHEN http_user_agent LIKE '%DBeaver%' THEN 'DBeaver'
            WHEN client_name LIKE '%Python%' THEN 'Python Script'
            ELSE concat(client_name, ' (', initial_user, ')')
        END AS source,
        formatReadableSize(memory_usage) AS memory_used,
        ProfileEvents.Values[indexOf(ProfileEvents.Names, 'UserTimeMicroseconds')] / 1000000 AS user_cpu_sec,
        substring(query, 1, 100) AS short_query
    FROM system.query_log
    WHERE type = 'QueryFinish'
      AND (query ILIKE '%rmv_l5_task_completion_v2%' OR query ILIKE '%mv_fact_task_vx%')
      AND query_start_time >= $__fromTime AND query_start_time <= $__toTime
      AND query NOT LIKE '%system.query_log%'
    ORDER BY query_start_time DESC
    LIMIT 5;
    ```
*   **說明**: 只顯示最新5筆 L5 查詢。`Duration (sec)` 欄位即為使用者等待時間。`source` 欄位標示查詢來源（Superset / DBeaver / Python）。

---

## 區塊四：Benchmark-Driven Panels (基準測試衍生面板)

以下 4 個面板依據 `monitoring_architecture_and_status.md` 壓測結果中識別出的監控缺口新增，對應報告 §3 ~ §6 之持續觀測需求。

### Panel 4.1: Query Latency Distribution（查詢延遲分佈）

對應報告 §3（查詢延遲與吞吐量）、§6（瓶頸定位）。區分 Pivot Model 與 Standard Model 延遲趨勢，持續觀測 P95 是否超出 1,000 ms 閾值。

| 設定項目 | 值 |
| :--- | :--- |
| **Data Source** | ClickHouse |
| **Chart Type** | Time series |
| **Unit** | Milliseconds (ms) |
| **Min interval** | 1m |
| **Draw style** | Points |
| **Point size** | 4 |

**查詢語法（SQL）**：

```sql
SELECT
    query_start_time AS time,
    query_duration_ms AS "Duration (ms)",
    CASE
        WHEN query LIKE '%UNION ALL%SELECT%status_name%' THEN 'Pivot Model'
        ELSE 'Standard Model'
    END AS model
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query ILIKE '%gold.rmv_l5_task_completion_v2%'
  AND query NOT LIKE '%system.query_log%'
  AND query_start_time >= $__fromTime AND query_start_time <= $__toTime
ORDER BY query_start_time
```

**Grafana 設定步驟**：

1. **紅綠分色**（Field Overrides）：
   - 右側面板 → **Overrides** 頁籤
   - 點 **+ Add field override** → 選 **Fields with name** → 輸入 `Pivot Model`
   - 點 **+ Add override property** → 選 **Standard options > Color scheme** → Fixed: `red`
   - 再次 **+ Add field override** → 選 **Fields with name** → 輸入 `Standard Model`
   - **+ Add override property** → **Standard options > Color scheme** → Fixed: `green`

2. **1000ms 紅線**（Thresholds）：
   - 右側面板 → **Standard options** 區塊
   - 找到 **Thresholds** → 點 **+ Add threshold**
   - 值輸入 `1000`，顏色選 `Red`
   - 上方 **Show thresholds** 選 **As lines**（非 As filled regions）

3. **確認 Unit**：
   - **Standard options → Unit** → 搜尋 `milliseconds` → 選 `Milliseconds (ms)`

---

### Panel 4.2: Real-time QPS（即時查詢吞吐量）

對應報告 §3。監控每分鐘查詢吞吐量，觀測是否低於 10 QPS 下限。

| 設定項目 | 值 |
| :--- | :--- |
| **Data Source** | ClickHouse |
| **Chart Type** | Time series |
| **Unit** | `short`（Grafana 無內建 QPS 單位，使用 short 即可） |
| **Min interval** | 1m |
| **Draw style** | Bars |
| **Line width** | 1 |
| **Fill opacity** | 30 |

**查詢語法（SQL）**：

SQL 已在 `count() / 60` 處將每分鐘查詢數換算為每秒，輸出值即為 QPS。

```sql
SELECT
    toStartOfMinute(query_start_time) AS time,
    count() / 60 AS "QPS"
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query ILIKE '%gold.rmv_l5_task_completion_v2%'
  AND query NOT LIKE '%system.query_log%'
  AND query_start_time >= $__fromTime AND query_start_time <= $__toTime
GROUP BY time
ORDER BY time
```

> Grafana 內建的 `req/s` 單位位於 **Standard options → Unit → Throughput → requests/sec (reqps)**。此面板因 SQL 已完成換算，選 `short` 或 `reqps` 皆可，差異僅在 Y 軸標籤顯示。

**10 QPS 綠色基準線設定步驟**：

1. 右側面板 → **Standard options** → **Thresholds**
2. 將預設的 Base（綠色）保留
3. 點 **+ Add threshold** → 值輸入 `10`，顏色選 `Green`
4. 上方 **Thresholds mode** 改為 **Absolute**
5. **Show thresholds** 選 **As lines**
6. 此時圖上出現一條綠色水平線，位於 QPS = 10 處
7. 柱子低於此線 = 吞吐量不足

---

### Panel 4.3: Per-Query CPU Time vs Duration（CPU 時間 vs 查詢延遲）

對應報告 §5（Per-Query 資源消耗）。兩者差距即為 Disk I/O 等待與查詢排隊時間。

| 設定項目 | 值 |
| :--- | :--- |
| **Data Source** | ClickHouse |
| **Chart Type** | Time series |
| **Unit** | Milliseconds (ms) |
| **Min interval** | 1m |
| **Draw style** | Points |
| **Point size** | 3 |

**查詢語法（SQL）**：

```sql
SELECT
    query_start_time AS time,
    ProfileEvents['UserTimeMicroseconds'] / 1000 AS "CPU User (ms)",
    query_duration_ms AS "Total Duration (ms)",
    query_duration_ms - (ProfileEvents['UserTimeMicroseconds'] / 1000) AS "I/O Wait (ms)",
    formatReadableSize(memory_usage) AS "Memory"
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query ILIKE '%gold.rmv_l5_task_completion_v2%'
  AND query NOT LIKE '%system.query_log%'
  AND query_start_time >= $__fromTime AND query_start_time <= $__toTime
ORDER BY query_start_time
```

**Field Overrides**：

| Override 條件 | 設定 |
| :--- | :--- |
| Field: `CPU User (ms)` | Color: `orange`，Axis: Left |
| Field: `Total Duration (ms)` | Color: `blue`，Axis: Left |
| Field: `I/O Wait (ms)` | Color: `green`，Axis: Left |
| Field: `Memory` | 隱藏（僅 Tooltip 中顯示） |

**Tooltip**：設定為 `All`，hover 時同時顯示 CPU、Duration、I/O Wait、Memory。

**顏色判讀**：橘色（CPU 運算）+ 綠色（I/O 等待）≈ 藍色（總延遲）。綠色佔比高代表瓶頸在磁碟 I/O，橘色佔比高代表瓶頸在 CPU 運算。

---

### Panel 4.4: Table Storage Overview（表容量與壓縮比）

對應報告 §4（資料壓縮比）。追蹤各表資料量增長與壓縮比變化。

| 設定項目 | 值 |
| :--- | :--- |
| **Data Source** | ClickHouse |
| **Chart Type** | Table |
| **Min interval** | — (每次載入即更新) |

**查詢語法（SQL）**：

```sql
SELECT
    database AS "Database",
    table AS "Table",
    formatReadableSize(sum(data_uncompressed_bytes)) AS "Uncompressed",
    formatReadableSize(sum(data_compressed_bytes)) AS "Compressed",
    round(sum(data_uncompressed_bytes) / sum(data_compressed_bytes), 2) AS "Ratio",
    formatReadableQuantity(sum(rows)) AS "Rows",
    count() AS "Parts"
FROM system.parts
WHERE active = 1
  AND database IN ('bronze', 'silver', 'gold')
  AND (table LIKE 'common%' OR table LIKE 'bpm%' OR table LIKE 'rmv%')
GROUP BY database, table
HAVING sum(data_uncompressed_bytes) > 1048576
ORDER BY sum(data_uncompressed_bytes) DESC
```

> 僅顯示 `common_*`、`bpm_*`、`rmv_*` 開頭之表，排除 Silver 層 `.inner_id.*` 內部表與 `sync_*`、`_sync_*` 系統表。

**Column Overrides**：

| 欄位 | 設定 |
| :--- | :--- |
| `Database` | Width: 80px |
| `Table` | Width: auto |
| `Ratio` | Unit: `short`，Decimals: 2，Thresholds: Green > 3，Yellow > 6，Red > 10 |
| `Rows` | Align: right |
| `Parts` | Align: right |

---

## Dashboard 佈局藍圖（更新版）

```text
+---------------------------------------------------------------------------------------+
| Row 1: Macro Health (系統大盤)                                                         |
+----------------------+----------------------+-----------------------------------------+
| [1.1] CPU Load %     | [1.2] Mem Avail %    | [3.1] Background Tasks                  |
+----------------------+----------------------+-----------------------------------------+

+---------------------------------------------------------------------------------------+
| Row 2: L5 Query Impact (查詢影響)                                                      |
+-------------------------------------------+-------------------------------------------+
| [2.1] CPU Consumption (CH vs Sys)         | [2.2] Memory Allocation (OS vs Internal)  |
+-------------------------------------------+-------------------------------------------+

+---------------------------------------------------------------------------------------+
| Row 3: Deep Dive (深度剖析)                                                             |
+----------------------+----------------------+-----------------------------------------+
| [2.3] Disk I/O Rates | [3.2] Mem Peaks      | [3.3] Expensive Queries                 |
+----------------------+----------------------+-----------------------------------------+

+---------------------------------------------------------------------------------------+
| Row 4: Benchmark Metrics (基準測試指標) ← 新增                                          |
+-------------------------------------------+-------------------------------------------+
| [4.1] Query Latency Distribution          | [4.2] Real-time QPS                       |
| (Pivot vs Standard, 1000ms threshold)     | (QPS bar chart, 10 QPS threshold)         |
+-------------------------------------------+-------------------------------------------+

+---------------------------------------------------------------------------------------+
| Row 5: Resource & Storage (資源與儲存) ← 新增                                           |
+-------------------------------------------+-------------------------------------------+
| [4.3] Per-Query CPU vs Duration           | [4.4] Table Storage Overview              |
| (CPU / Duration / I/O Wait overlay)       | (compression ratio table)                 |
+-------------------------------------------+-------------------------------------------+
```

---

## ⚡ 故障排除小撇步
1.  **無數據 (No Data)**: 檢查 Panel -> Query Options -> **Min interval = 1m**。
2.  **記憶體負數**: 確保 B 查詢使用了 `clamp_min(..., 0)`。
3.  **Label 錯位**: 若系統指標出不來，檢查 `instance="docker-host"`。
4.  **Pivot / Standard 分類不準**: Panel 4.1 以 `query LIKE '%UNION ALL%SELECT%status_name%'` 判斷 Pivot，若 SQL 結構變更需同步修改條件。
5.  **QPS 為 0**: Panel 4.2 以分鐘為粒度統計，若選擇時間範圍內無 L5 查詢則顯示空白屬正常。
