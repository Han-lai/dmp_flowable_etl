# Superset 儀表板整合手冊 (Superset Dashboard Manual)

> **版本**: 1.0  
> **最後更新**: 2026-02-03  
> **對應 Cube**: L5DashboardCompletion / L5DashboardSummary

---

## 📊 1. 資料源配置 (Data Source)

### Cube.js 連接 (推薦)
*   **端點**: `http://your-cubejs-server:4000/cubejs-api/v1`
*   **Cube**: `L5DashboardCompletion`
*   **優點**: 已內建複雜的比例計算 (Sum(Done)/Sum(Total))，Superset 僅需展示。

### ClickHouse 直連 (備選/除錯)
*   **資料源**: `gold.rmv_l5_task_completion`
*   **連接字串**: `clickhouse://default:default@REDACTED_IP:8121/gold`

---

## 🎯 2. 圖表配置範例 (Charts)

### 📊 長條圖 - 任務分布 (Todo/Doing/Done)
*   **圖表類型**: Stacked Bar Chart
*   **X 軸**: `snapshotDate` (時間維度)
*   **Y 軸 (SUM 聚合)**:
    *   `totalTask` (總量)
    *   `todoTask` (Todo)
    *   `doingTask` (Doing)
    *   `doneTask` (Done)
*   **分組**: `vxScope` (V1/V2/V3)
*   **顏色**: Todo(橙 `#FFA500`), Doing(藍 `#1E90FF`), Done(綠 `#32CD32`)

### 📈 折線圖 - 完成率趨勢
*   **圖表類型**: Line Chart
*   **X 軸**: `snapshotDate`
*   **Y 軸 (AVG 聚合)**:
    *   `completionRate` (完成率 %)
    *   `progressRate` (執行率 %)
*   **注意**: 這裡選 `AVG` 是因為 Cube.js 在聚合時已正確算好百分比，Superset 僅需對單一快照點取均值。

### 📋 數據明細表 (Details)
*   **圖表類型**: Table
*   **階層維度**: `region` > `plant` > `factory` > `line`
*   **指標**: 所有數量 (SUM) 與 百分比 (AVG)。

---

## ⚙️ 3. 聚合函數選擇規則 (CRITICAL)

| 指標類型 | Superset 聚合 | 範例 |
| :--- | :--- | :--- |
| **數量 (Count/Qty)** | **SUM** | `totalTask`, `doneTask` |
| **百分比 (%)** | **AVG** | `completionRate`, `doingDoneRate` |

> [!WARNING]
> **絕對不要** 對百分比欄位使用 `SUM`。例如 `80% + 50% = 130%` 是無意義的數值。

---

## 🎨 4. 視覺化建議

*   **千分位**: 數量欄位建議使用 `,d`。
*   **百分比**: 建議使用 `.1%` 並帶有後綴。
*   **篩選器**: 建議設置 `snapshotDate` 為最近 30 天，並啟用 `region` 到 `plant` 的階層連動篩選。
