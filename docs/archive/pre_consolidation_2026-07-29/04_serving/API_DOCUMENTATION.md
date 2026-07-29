# Flowable L5 Insight API - 開發者文件 (API Documentation)

本文件提供 **L5 任務完成率報表 API** 的技術細節、端點說明、請求與回應範例，以及錯誤處理說明。

---

## 1. API 概覽 (Overview)

**Flowable L5 Insight API** 是一個基於 FastAPI 構建的高效能報表服務。它直接從 ClickHouse Gold Layer (`gold.rmv_l5_task_completion`) 讀取數據，並在 Python 層進行動態週期聚合（Monthly, Weekly, Daily），產出結構化的生產效率報表。

- **主要功能**: 提供特定月份的每月、每週（ISO 週）及每日（最後 7 天）的任務指標（Total, Todo, Doing, Done, Acc）。
- **版本**: `1.2.0`
- **內建文件 (Swagger)**: `http://<CLICKHOUSE_HOST>:7088/docs`

---

## 2. 基礎資訊 (Base URL & Auth)

### 基礎網址 (Base URL)
所有 API 請求應發送至：
`http://<CLICKHOUSE_HOST>:7088`

### 身份驗證 (Authentication)
目前此 API 為內部區域網路使用，**無需額外認證標頭** (No Auth Token Required)。

---

## 3. 端點說明 (Endpoints)

### A. L5 任務完成率報表 (GET)
透過 Query Parameters 獲取報表內容。

- **URL**: `/api/l5/task-report`
- **Method**: `GET`
- **Query Parameters**:

| 參數 | 必填 | 類型 | 預設值 | 範例 | 說明 |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **month** | 是 | string | - | `2025-12` | 報表目標月份 (yyyy-MM) |
| **vxtype** | 否 | string | `ALL` | `V1`, `V3` | Vx 任務類型過濾 |
| **region** | 否 | string | `ALL` | `CNE`, `CNS` | 廠區區域過濾 (Site) |
| **plant** | 否 | string | `ALL` | `WJ2`, `DG3` | 廠別過濾 |
| **factory** | 否 | string | `ALL` | `NBU`, `SMT` | 廠部過濾 |
| **line** | 否 | string | `ALL` | `E5`, `ST02` | 線體過濾 |

---

### B. L5 任務完成率報表 (POST)
透過 JSON Body 獲取報表內容，適合包含大量篩選條件的場景。

- **URL**: `/api/l5/task-report`
- **Method**: `POST`
- **Request Body (JSON)**:

```json
{
  "month": "2025-12",
  "vxtype": "ALL",
  "region": "ALL",
  "plant": "WJ2",
  "factory": "ALL",
  "line": "ALL"
}
```

---

## 4. 回應資料結構 (Response Schema)

API 成功回應時（`200 OK`）將返回以下結構：

```json
{
  "status": "success",
  "data": {
    "month": "2025-12",
    "columns": {
      "month": "Dec.",
      "weeks": ["W1", "W52", "W51"],
      "days": ["2025-12-31", "2025-12-30", ...]
    },
    "rows": [
      {
        "vxtype": "ALL",
        "region": "ALL",
        "plant": "ALL",
        "factory": "ALL",
        "line": "ALL",
        "status": "Done",
        "month": { "qty": 150, "percentage": "85.0%" },
        "weeks": {
          "W1": { "qty": 20, "percentage": "90.0%" }
        },
        "days": {
          "2025-12-31": { "qty": 5, "percentage": "100.0%" }
        }
      }
    ]
  }
}
```

---

## 5. cURL 呼叫範例 (Examples)

### GET 範例 (依月份查詢)
```bash
curl -X 'GET' \
  'http://<CLICKHOUSE_HOST>:7088/api/l5/task-report?month=2025-12&plant=WJ2' \
  -H 'accept: application/json'
```

### POST 範例 (複雜過濾)
```bash
curl -X 'POST' \
  'http://<CLICKHOUSE_HOST>:7088/api/l5/task-report' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "month": "2025-12",
  "plant": "DG3",
  "factory": "SMT"
}'
```

---

## 6. 錯誤處理 (Error Handling)

API 使用標準 HTTP 狀態碼：

| 狀態碼 | 名稱 | 說明 |
| :--- | :--- | :--- |
| **200** | OK | 查詢成功。 |
| **400** | Bad Request | 月份格式錯誤（需為 yyyy-MM）或參數不合法。 |
| **422** | Unprocessable Entity | JSON Body 驗證失敗（模型欄位缺失）。 |
| **500** | Internal Server Error | ClickHouse 連線失敗或查詢超時。 |

### 錯誤回應範例 (500)
```json
{
  "detail": "Database connection failed"
}
```

---
*Last Updated: 2026-05-28*
