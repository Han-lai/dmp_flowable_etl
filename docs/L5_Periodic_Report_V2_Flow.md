# L5 週期報表 V2 架構圖 (Data Flow)

這份文件說明了 **L5TaskPeriodicV2** 模型如何透過 Cube.js SQL Injection 機制，達成 ClickHouse View 做不到的「動態邏輯判斷」。

## 核心資料流 (Data Flow)

```mermaid
graph TD
    User([Superset User]) -->|1. 選擇日期: 2025-12| SS[Superset UI]
    SS -->|2. 發API請求| API[Cube.js API]
    
    subgraph Cube Layer [Cube.js Middleware]
        API -->|3. 讀取模型| Model[cube_l5_task_periodic_v2.js]
        Model -->|4. SQL 生成與注入| GenSQL[SQL Generator]
        
        note1[關鍵點: Filter 在這裡就注入了!\n而不是等到資料庫才過濾]
        Model -.-> note1
    end
    
    GenSQL -->|5. 發送完整 SQL| CH[(ClickHouse DB)]
    
    subgraph Database Layer [ClickHouse Execution]
        SQL[接收到的 SQL] --> CTE_Base[CTE 'base'\n(WHERE snapshot_date...)]
        CTE_Base -->|已過濾的數據| CTE_Params[CTE 'params'\n(max_date detection)]
        
        CTE_Params -->|推論: 都是過去日期| Logic{模式判斷}
        Logic -->|History Mode| Anchor1[Anchor = 月底]
        Logic -->|Current Mode| Anchor2[Anchor = 今天]
        
        Anchor1 --> Agg[三層級聚合\nMonth / Week / Day]
        Anchor2 --> Agg
    end
    
    Agg -->|6. 回傳結果| API
    API -->|7. 回傳 JSON| SS
```

## 為什麼 V2 模型 (Cube Injection) 可行？

對比我們稍早測試失敗的 View 方案：

| 方案 | 運作方式 | 結果 | 原因 |
| :--- | :--- | :--- | :--- |
| **ClickHouse View** | 先算 CTE (無篩選) -> 再外層 WHERE | ❌ 失敗 | CTE 永遠抓到最新日期 (Today)，因為 Filter 進不去內部。 |
| **Cube V2 (此方案)** | **先將 Filter 寫入 CTE** -> 再送給 DB 算 | ✅ 成功 | CTE 算的時候已經是「篩選過」的範圍，能正確判斷歷史。 |

## SQL 結構示意

Cube 生成並送給 ClickHouse 的 SQL 大致長這樣：

```sql
WITH 
    base AS (
        SELECT * FROM gold.rmv_l5_task_completion
        -- [關鍵] Cube 在這裡就幫您加上了 WHERE
        WHERE snapshot_date >= '2025-12-01' AND snapshot_date <= '2025-12-31'
    ),
    params AS (
        -- 因為 base 已經被篩選過，這裡抓到的 max 就是 12/31
        SELECT max(snapshot_date) as max_filtered_date FROM base
    )
    -- ... 後續邏輯就能正確走到 "History Mode"
```
