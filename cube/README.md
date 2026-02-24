# Cube.js 語意層

> **最後更新**: 2026-02-24  
> **資料來源**: `gold.rmv_l5_task_completion_v2`

## 架構

```
ClickHouse (Gold Layer)
        │
        ▼
    Cube.js
    ├── REST API (port 4002)
    ├── Playground (port 4003)
    └── Model (2 個 Active Cube)
        │
        ▼
    Superset Dashboard
```

## 目錄結構

```
cube/
├── docker-compose.yml           # Cube.js 部署設定
├── .env.example                 # 環境變數範本
├── README.md                    # 本檔案
└── model/
    ├── cubes/
    │   ├── cube_l5_task_periodic_v2.js        # ✅ L5 週期報表 (Active)
    │   ├── cube_l5_task_periodic_v2_pivot.js   # ✅ L5 狀態比較 (Active)
    │   ├── README_L5_DASHBOARD_CUBE.md        # 模型說明
    │   └── archive/                            # 舊版模型 (5 個, 已棄用)
    └── views/
        └── view_historical_trends.js           # 歷史趨勢 View
```

## Active Models

### 1. `cube_l5_task_periodic_v2.js` — 週期性報表
- **資料來源**: `gold.rmv_l5_task_completion_v2`
- **功能**: L5 任務完成率週期報表
- **特色**:
  - 7 天滾動分母（避免週末波動）
  - Triple-OR 時間篩選（相容 Dashboard / Chart 不同格式）
  - 動態時間模式（D0 / W-pattern / Month）

### 2. `cube_l5_task_periodic_v2_pivot.js` — 狀態比較報表
- **資料來源**: `gold.rmv_l5_task_completion_v2`
- **功能**: L5 任務狀態比較（Pivot 展開）
- **特色**:
  - 結合 V2 進階邏輯與 Pivot 結構
  - 支援 6 種狀態橫向比較
  - 支援歷史時點回溯查詢

## 快速開始

### 啟動

```powershell
cd cube
docker compose up -d
```

### 存取 Playground

瀏覽器開啟：http://localhost:4003

### API 測試

```bash
curl http://localhost:4002/cubejs-api/v1/load \
  -H "Authorization: REDACTED_SECRET" \
  -G --data-urlencode 'query={"measures":["L5TaskPeriodicV2.totalTask"]}'
```

## 環境設定

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `CUBEJS_DB_TYPE` | `clickhouse` | 資料庫類型 |
| `CUBEJS_DB_HOST` | `REDACTED_IP` | ClickHouse 主機 |
| `CUBEJS_DB_PORT` | `8121` | ClickHouse HTTP Port |
| `CUBEJS_DB_USER` | `default` | 使用者 |
| `CUBEJS_DB_NAME` | `silver` | 預設 DB |
| `CUBEJS_API_SECRET` | (見 .env.example) | API 金鑰（生產環境請更換） |

## 注意事項

1. **ClickHouse 連線**: 確保 ClickHouse 允許來自 Docker 容器的連線
2. **API Secret**: 生產環境請更換 `CUBEJS_API_SECRET`
3. **Cube 重啟**: 修改 Model 後需要重啟 Cube.js 服務
4. **時區**: 預設使用 UTC，如需調整請設定 `CUBEJS_SCHEDULED_REFRESH_TIMEZONE`

## 詳細模型說明

請參閱 [README_L5_DASHBOARD_CUBE.md](model/cubes/README_L5_DASHBOARD_CUBE.md)。
