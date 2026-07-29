# ClickHouse L5 效能壓測操作手冊 (Docker 環境原生版)

本文件敘述如何使用 ClickHouse 官方原生之 `clickhouse-benchmark` 命令列工具，對部署於 Docker 容器環境下之 ClickHouse 服務進行高併發效能壓力測試。

---

## 1. 壓測環境建置

本操作標準程序 (SOP) 不依賴外部 Python 封裝腳本，採直接執行 ClickHouse 原生 CLI 與 SQL 實體檔案之方式進行測試，以確保環境特徵之純粹度。

### 1.1 建立查詢腳本 (`queries.sql`)
測試前需於主機端備妥包含目標測試 SQL 語句之檔案，以模擬前端客戶端實務上發出之 Query 結構。

> **架構說明：為何採用長格式 SQL 語法？**
> 在 `queries.sql` 中的測試語法並不採用簡易之 `SELECT *`，而是使用結合 `WITH params AS ...` 與多重 `UNION ALL` 區塊之進階型 CTE (Common Table Expression) 語句。
> 其原因為前端儀表板 (Superset / BI) 於渲染圖表時，雖從 2-Tier 物理表中讀取底層匯總指標，但仍需仰賴此段動態攤平 (Pivot) 語法將二階層資料轉化為「月 (Month)」、「週 (Week)」、「日 (Day)」等立體時間維度矩陣。採用此類符合真實高運算負荷之長格式語法，方能精準衡量儀表板載入時之實際伺服器極限。

請建立 `queries.sql`，並置於 `scripts/performance/` 目錄下：
```sql
WITH params AS (SELECT max(snapshot_date) as max_filtered_date, today() as sys_today FROM gold.rmv_l5_task_completion WHERE ...), 
calc_anchor AS (...), 
base AS (...)
SELECT 'Month' as granularity ... FROM base ... 
UNION ALL 
SELECT 'Week' as granularity ... FROM base ...
UNION ALL 
SELECT 'Day' as granularity ... FROM base ...
UNION ALL 
SELECT 'FilterRef' as granularity ... ;
```

---

## 2. 壓測執行指令

透過 Docker 終端執行命令，將 SQL 腳本作為標準輸入 (`stdin`) 導入至 `clickhouse-benchmark` 進行測試。

### 2.1 基礎指令格式
```bash
docker exec -i <容器名稱或ID> clickhouse-benchmark --user=<角色> --password=<密碼> --concurrency=<併發人數> --iterations=<查詢總次數> < queries.sql
```

### 2.2 實務執行範例 (針對 <CLICKHOUSE_HOST> 主營運主機)
**進行 100 併發高壓負載測試**：
```bash
docker exec -i clickhouse clickhouse-benchmark \
    --user=default \
    --password=<CLICKHOUSE_PASSWORD> \
    --concurrency=100 \
    --iterations=500 \
    --randomize < /路徑/到/您的/scripts/performance/queries.sql
```
> **參數定義**：
> - `--concurrency=100`：模擬 100 個獨立連線同步提出查詢請求。
> - `--iterations=500`：設定於該次壓力測試作業期間需完成之查詢配額總數。
> - `--randomize`：啟用陣列隨機引擎，亂序讀取 `queries.sql` 內之陳述式執行，避免快取機制造成傾斜現象，提升測試客觀準確度。

---

## 3. 測試報告解析

命令執行完竣後，原生工具將傳回效能分析報告至標準輸出 (STDOUT)，工程人員須評估以下核心指標：

```text
Queries executed: 500.

localhost:9000, version 23.3.1.2823

QPS: 84.580           <-- 【效能核心基準】每秒平均可處置之查詢總量 
Queries/sec: 84.580

Latency:
    min       38.000 ms
    10%       85.100 ms
    50%      396.400 ms   <-- P50中位數: 50% 比例之查詢可於 0.39 秒內完成回傳
    90%      480.000 ms
    95%      543.100 ms   <-- P95分位數: 確保 95% 比例之查詢時間上限為 0.54 秒
    99%      616.400 ms   <-- P99分位數: 最極端 1% 異常狀態下之最大延遲時間 (約 0.61 秒)
```

---

## 4. 系統資源控制機制觀測

當執行達 100 人上限之高壓連線測試時，系統底層將自行啟動預設之資源防護組態 (`config.d/max_queries.xml` 與 `users.d/max_queries_profile.xml`)：

1. **併發控制配額 (`max_concurrent_queries=50`)**：系統優先配發實體 CPU 運算資源予前 50 筆活躍狀態連線。
2. **連線佇列防禦機制 (`queue_max_wait_ms=30000`)**：超額之連線請求將被轉換至休眠佇列 (Queue) 中等候處理。此排隊行為對應用層透明，不會觸發拒絕服務錯誤 (Connection Refused)。
3. **指標判序意義**：上述分析中之 P99 延遲數據，其返回結果已涵蓋「佇列閒置等待期」加上「實質資源運算期」之總和，屬評估大量平行使用者綜合操作體驗最具參考性之技術指標。
