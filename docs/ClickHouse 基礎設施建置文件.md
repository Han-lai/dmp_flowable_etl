# ClickHouse 基礎設施建置文件

## 0. 定位

本文說明 **ClickHouse 容器本身的建置與設定**：客製 image、ODBC 連線設定、server/user 層級設定檔、部署步驟。

與 [`docs/SYSTEM_REFERENCE.md`](SYSTEM_REFERENCE.md) 分工：該文件說明 ETL 架構、業務邏輯與資料管線操作；本文只說明 ClickHouse 容器本身怎麼建置起來、怎麼設定。兩份文件互補，不重複。

**閱讀對象**：需要建置、重建或維運 ClickHouse 容器的工程師。

**鐵律**：連線資訊一律環境變數，本文與程式碼皆不寫死內部主機名稱、IP 或密碼。

---

## 1. 容器架構

ClickHouse 使用**客製 image**，而非官方原生映像，原因是要內建 Native ODBC 連線能力（見 [`SYSTEM_REFERENCE.md` §1.4](SYSTEM_REFERENCE.md#14-技術棧與版本)：ODBC 吞吐量約為 JDBC 方案的 2.7 倍）。

**建置來源**：`infra/clickhouse/odbc/Dockerfile`，以 `clickhouse/clickhouse-server:25.8.18.1` 為基礎，額外安裝：
- `unixodbc`
- Microsoft `ODBC Driver 18 for SQL Server`
- `clickhouse-odbc-bridge`（**版本必須與 ClickHouse server 完全一致**，否則 bridge 無法啟動）

**啟動方式**：`infra/clickhouse/odbc/docker-compose-odbc.yml`

| 項目 | 設定 |
|---|---|
| 對外埠（HTTP） | `8122:8123` |
| 對外埠（Native TCP） | `9002:9000` |
| 對外埠（Prometheus metrics） | `9364:9363` |
| 資料持久化 | named volume `clickhouse-odbc-data:/var/lib/clickhouse` |
| 網路 | 獨立 bridge network `clickhouse-net` |
| 檔案描述符上限 | `nofile: 262144`（大量並行 ODBC 連線需要） |

啟動時容器內會動態寫入 `<listen_host>0.0.0.0</listen_host>` 與 Prometheus `<endpoint>/metrics</endpoint>` 設定至 `config.d/config.xml`，讓外部網路可連線並支援 metrics 抓取。

---

## 2. ODBC 連線設定（`odbc.ini`）

檔案：`infra/clickhouse/odbc/odbc.ini`，定義 DSN 名稱 `MSSQL_DSN`（[`SYSTEM_REFERENCE.md`](SYSTEM_REFERENCE.md) 所有 `odbc()` 查詢與 `sync_unified_odbc.py` 皆引用此 DSN）。

```ini
[MSSQL_DSN]
Driver = ODBC Driver 18 for SQL Server
Server = <MSSQL 主機位址>,<port>
TrustServerCertificate = yes
Encrypt = no
LoginTimeout = 30
```

| 欄位 | 說明 |
|---|---|
| `Driver` | 對應 Dockerfile 安裝的 `ODBC Driver 18 for SQL Server` |
| `Server` | MSSQL 主機位址與埠，內部網段，不寫入本文 |
| `TrustServerCertificate` | `yes`，內網連線略過憑證鏈驗證 |
| `Encrypt` | `no`，內網連線不加密傳輸 |
| `LoginTimeout` | 30 秒 |

**帳密不寫在 `odbc.ini`**：`Uid`/`Pwd` 由 Python 端（`sync_unified_odbc.py` 的 `build_odbc_conn()`）在執行期動態組進連線字串，`odbc.ini` 本身不含任何憑證。

**ODBC bridge 斷線（`IMC06`）的實際防護機制在 ClickHouse 端，不在 `odbc.ini`**：`sync_unified_odbc.py` 以 `odbc_bridge_use_connection_pooling: 0` 關閉 bridge 連線池（[:34-36](../scripts/etl/sync_unified_odbc.py#L34-L36)），避免壞死連線被後續查詢重用而拋出 `IMC06`（"connection is broken and recovery is not possible"）；仍發生時由 `StaleOdbcConnectionError` 攔截，不會嘗試切窗重試（見 [`SYSTEM_REFERENCE.md` §2.3](SYSTEM_REFERENCE.md#23-資料拉取的自適應切窗mssql-減壓機制)）。

---

## 3. Server 層級設定檔：`config.d/max_queries.xml`（併發總閘門）

檔案位於 `infra/clickhouse/config.d/`，掛載至容器內 `/etc/clickhouse-server/config.d/`。

```xml
<clickhouse>
    <max_concurrent_queries>50</max_concurrent_queries>
</clickhouse>
```

限制伺服器同時處理的查詢數上限為 50，避免容器記憶體有限時被大量重量級查詢（如 CROSS JOIN 報表）同時壓垮導致 OOM。

**部署機制**：`docker-compose-odbc.yml` 掛載的是主機路徑 `${VOLUMES_ROOT}/clickhouse-odbc/config`，而非直接掛 repo 內的 `infra/clickhouse/config.d/`。修改此設定檔後，必須先同步複製到主機的 `${VOLUMES_ROOT}/clickhouse-odbc/config/`，再重啟容器才會生效（見 §5.2）。

---

## 4. 使用者層級設定檔：`users.d/max_queries_profile.xml`（排隊機制）

檔案位於 `infra/clickhouse/users.d/`，掛載至容器內 `/etc/clickhouse-server/users.d/`。

```xml
<clickhouse>
    <profiles>
        <default>
            <queue_max_wait_ms>30000</queue_max_wait_ms>
        </default>
    </profiles>
</clickhouse>
```

與 §3 的 `max_concurrent_queries` 搭配：連線數超過 50 時，後續連線不會直接報 `Too many simultaneous queries` 錯誤，而是進入排隊，最多等待 30 秒。這是高併發（如百人壓力測試）情境下不噴錯的關鍵機制。

**部署機制**：`docker-compose-odbc.yml` 的 `volumes` 區塊需包含此掛載：

```yaml
volumes:
  - clickhouse-odbc-data:/var/lib/clickhouse
  - ${VOLUMES_ROOT}/clickhouse-odbc/config:/var/lib/clickhouse/server/config.d
  - ${VOLUMES_ROOT}/clickhouse-odbc/users:/var/lib/clickhouse/server/users.d
  - ${VOLUMES_ROOT}/clickhouse-odbc/odbc.ini:/etc/odbc.ini
```

---

## 5. 部署步驟

### 5.1 首次建置

```bash
# 1. 建立客製 image
cd infra/clickhouse/odbc
docker build -t clickhouse-server-odbc-image .

# 2. 在主機建立 VOLUMES_ROOT 目錄結構並放入設定檔
mkdir -p ${VOLUMES_ROOT}/clickhouse-odbc/config
mkdir -p ${VOLUMES_ROOT}/clickhouse-odbc/users
cp infra/clickhouse/config.d/*.xml ${VOLUMES_ROOT}/clickhouse-odbc/config/
cp infra/clickhouse/users.d/*.xml  ${VOLUMES_ROOT}/clickhouse-odbc/users/
cp infra/clickhouse/odbc/odbc.ini  ${VOLUMES_ROOT}/clickhouse-odbc/odbc.ini

# 3. 啟動容器
set -a && . infra/clickhouse/odbc/.env && set +a
docker-compose -f infra/clickhouse/odbc/docker-compose-odbc.yml up -d
```

### 5.2 設定檔異動後如何套用

修改 `infra/clickhouse/config.d/` 或 `infra/clickhouse/users.d/` 底下任何檔案後：

```bash
cp infra/clickhouse/config.d/*.xml ${VOLUMES_ROOT}/clickhouse-odbc/config/
cp infra/clickhouse/users.d/*.xml  ${VOLUMES_ROOT}/clickhouse-odbc/users/
docker-compose -f infra/clickhouse/odbc/docker-compose-odbc.yml restart clickhouse-odbc
```
