# ClickHouse Configuration for DMP Flowable

本資料夾集中管理保護 ClickHouse 免於 OOM (Out-of-Memory) 崩潰的關鍵設定檔。這些設定透過「限制最高平行運算」加上「人性化排隊機制」，在不中斷服務的前提下撐過尖峰時段。

## 部署與掛載方式

當您在任意伺服器（例如 REDACTED_IP）上啟動或重新建置 ClickHouse Docker 容器時，請**務必使用 Volume ( `-v` ) 將這兩個資料夾對應掛載進去**。

### Docker Run 範例：

```bash
docker run -d \
  --name clickhouse-server \
  -p 8123:8123 -p 9000:9000 \
  -v /你的絕對路徑/infra/clickhouse/config.d:/etc/clickhouse-server/config.d \
  -v /你的絕對路徑/infra/clickhouse/users.d:/etc/clickhouse-server/users.d \
  clickhouse/clickhouse-server
```

*(如果您使用 `docker-compose.yaml`，請在 `volumes` 區塊加入相同的掛載路徑。)*

## 設定檔說明

1. **`config.d/max_queries.xml` (伺服器總閘門)**
   - 限制 `max_concurrent_queries = 50`。
   - 保護 4.5 GB RAM 的 Docker 容器不會因為 50 個以上的重量級 CROSS JOIN 報表連線而導致 OOM 報錯強制終止。

2. **`users.d/max_queries_profile.xml` (使用者排隊機制)**
   - 包含 `queue_max_wait_ms = 30000`。
   - 當連線數超過 50，後續湧入的連線不會直接報錯 `Too many simultaneous queries`，而是進入排隊（最多等待 30 秒）。這是確保在 100 人壓力測試下不噴錯的關鍵。
