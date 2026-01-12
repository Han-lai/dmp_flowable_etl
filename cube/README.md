# Cube.js 整合說明

## 架構

```
ClickHouse (Silver RMV)
        │
        ▼
    Cube.js
    ├── REST API (port 4002)
    ├── Playground (port 4003)
    └── Model (3 個 Cube)
        │
        ▼
    前端 Dashboard
```

## 目錄結構

```
cube/
├── model/                    # 數據模型（官方標準）
│   ├── cubes/               # Cube 定義
│   │   ├── cube_proc_task_node.js    # 任務節點
│   │   ├── cube_biz_event_info.js    # 業務事件
│   │   └── cube_proc_inst_node.js    # 流程實例
│   └── views/               # View 定義（對外 API 層）
│       └── .gitkeep
├── docker-compose.yml
└── README.md
```

**命名規範：**
- Cube 定義：`cube_` 前綴
- 複合指標：`metric_` 前綴
- 基礎定義用 `.yml`，複雜邏輯用 `.js`

## 快速開始

### 1. 啟動 Cube.js

```bash
cd cube
docker-compose up -d
```

### 2. 存取 Playground

開啟瀏覽器：http://localhost:4003

### 3. 測試 API

```bash
# 查詢在途任務數
curl http://localhost:4002/cubejs-api/v1/load \
  -H "Authorization: REDACTED_SECRET" \
  -G --data-urlencode 'query={"measures":["ProcTaskNode.inProgressTaskCount"]}'
```

## Cube Schema

### ProcTaskNode (任務節點)

**來源：** `silver.RMV_HI_PROC_TASK_NODE`

**維度：**
- taskId, procInstId, businessKey
- taskName, taskStatus, assignee, deptName
- factory, plant, lineName, region
- startTime, endTime, claimTime

**指標：**
- inProgressTaskCount - 在途任務數
- todoCount, doingCount, doneCount, doneAutoCount, cancelledCount
- autoCompleteRate - 自動完成率 (%)
- avgWorkDuration - 平均任務處理時長 (秒)

### BizEventInfo (業務事件)

**來源：** `silver.RMV_HI_BIZ_EVENT_INFO`

**維度：**
- businessKey, firstProcDefName
- factory, plant, lineName, region
- firstStartTime, finalEndTime

**指標：**
- inProgressEventCount - 在途業務事件數
- completedEventCount - 已完成業務事件數
- avgTotalDuration - 平均業務事件總歷時 (秒)

### ProcInstNode (流程實例)

**來源：** `silver.RMV_HI_PROCINST_NODE`

**維度：**
- procInstId, procDefName, businessKey
- depth, superId
- factory, plant, lineName, region
- procStatus, startTime, endTime

**指標：**
- inProgressCount - 在途流程數
- completedCount - 已完成流程數
- terminatedCount - 終止流程數

## 指標對應

| 指標 | Cube | Measure |
|------|------|---------|
| 在途業務事件總數 | BizEventInfo | inProgressEventCount |
| 在途任務總數 | ProcTaskNode | inProgressTaskCount |
| 事件自動完成率 | ProcTaskNode | autoCompleteRate |
| TASK_STATUS 分布 | ProcTaskNode | todoCount, doingCount, ... |
| 在途任務數-依廠區 | ProcTaskNode | inProgressTaskCount + plant 維度 |
| 在途任務數-依部門 | ProcTaskNode | inProgressTaskCount + deptName 維度 |
| 在途任務數-依人員 | ProcTaskNode | inProgressTaskCount + assignee 維度 |
| 平均業務事件總歷時 | BizEventInfo | avgTotalDuration |
| 平均任務處理時長 | ProcTaskNode | avgWorkDuration |
| 在途流程健康度快照 | BizEventInfo | inProgressEventCount + firstProcDefName 維度 |
| 依流程的自動完成率 | ProcTaskNode | autoCompleteRate + procDefName 維度 |

## 查詢範例

### 在途任務數 - 依廠區

```json
{
  "measures": ["ProcTaskNode.inProgressTaskCount"],
  "dimensions": ["ProcTaskNode.plant"],
  "order": { "ProcTaskNode.inProgressTaskCount": "desc" },
  "limit": 10
}
```

### 自動完成率 - 依流程

```json
{
  "measures": ["ProcTaskNode.autoCompleteRate", "ProcTaskNode.doneTotalForRate"],
  "dimensions": ["ProcTaskNode.procDefName"],
  "filters": [
    { "member": "ProcTaskNode.doneTotalForRate", "operator": "gte", "values": ["10"] }
  ],
  "order": { "ProcTaskNode.doneTotalForRate": "desc" },
  "limit": 10
}
```

### 歷史趨勢 - 每日在途任務數

```json
{
  "measures": ["ProcTaskNode.inProgressTaskCount"],
  "timeDimensions": [
    {
      "dimension": "ProcTaskNode.startTime",
      "granularity": "day",
      "dateRange": "last 30 days"
    }
  ]
}
```

## 注意事項

1. **ClickHouse 連線**：確保 ClickHouse 允許來自 Docker 容器的連線
2. **API Secret**：生產環境請更換 `CUBEJS_API_SECRET`
3. **Pre-aggregations**：首次查詢可能較慢，因為需要建立預聚合
4. **時區**：Cube.js 預設使用 UTC，如需調整請設定 `CUBEJS_SCHEDULED_REFRESH_TIMEZONE`
