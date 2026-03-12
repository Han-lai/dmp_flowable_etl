# 實作手冊 4：CubeJS 語義層維護與 FastAPI 接口手冊

本手冊詳述如何將 ClickHouse 的計算結果，透過語義層 (CubeJS) 與高性能後端 (FastAPI) 交付給前端展示。

---

## 1. CubeJS 語義建模實作
CubeJS 負責跨維度聚合與數據翻譯。

### **1.1 Triple-OR 日期相容性過濾**
為了解決不同前端組件傳入的日期格式差異，我們在 `sql` 片段使用了「三層 OR」判定：
```javascript
// cube_l5_task_periodic_v2.js
WHERE (
    ${FILTER_PARAMS.L5TaskPeriodicV2.snapshotDate.filter('toString(snapshot_date)')}
    OR ${FILTER_PARAMS.L5TaskPeriodicV2.snapshotDate.filter("formatDateTime(snapshot_date, '%Y-%m-%d 00:00:00')")}
    OR ${FILTER_PARAMS.L5TaskPeriodicV2.snapshotDate.filter("formatDateTime(snapshot_date, '%Y-%m-%dT00:00:00.000Z')")}
)
```

### **1.2 7 天滾動分母 (Smoothing)**
為了平滑週末數據對完成率造成的劇烈波動，系統採用了窗口函式來計算分母：
```sql
sum(total_qty) OVER (
    PARTITION BY vx_type, region, plant, factory, line 
    ORDER BY snapshot_date_real ASC 
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
) as acc_total_qty
```

---

## 2. FastAPI 高性能數據服務
API 負責複雜的格式轉換（如行列轉置）與多週期數據彙整。

### **2.1 Pydantic 資料結構定義**
```python
class L5ReportRequest(BaseModel):
    month: str # yyyy-MM
    plant: Optional[str] = "ALL"
    # ... 其他五階維度
```

### **2.2 核心聚合技術：`argMax`**
在計算 Monthly/Weekly 的「累積在途」時，不能直接 `sum`。我們使用 `argMax` 取得該週期最後一天的快照值：
```sql
SELECT
    concat('W', toString(toWeek(snapshot_date, 1))) as label,
    sum(total_task) as total,
    argMax(acc_todo_doing, snapshot_date) as acc -- 取得該週最後一天的在途量
FROM gold.rmv_l5_task_completion
GROUP BY label
```

---

## 3. 開發者偵錯建議
*   **Swagger 文件**：存取 `http://localhost:8000/docs` 可直接測試所有 API 接口。
*   **CubeJS Playground**：存取 `http://localhost:4003` 可視覺化調整維度與指標。

---
**文件維護資訊**
*   **版本號**：v1.0.0
*   **更新日期**：2026-03-12
*   **維護人員**：albee
