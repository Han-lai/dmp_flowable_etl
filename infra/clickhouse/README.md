# ClickHouse & JDBC Bridge Infrastructure Setup Guide

This guide describes how to set up the ClickHouse Server and JDBC Bridge infrastructure from scratch, providing seamless connectivity to MSSQL data sources.

---

## 1. Directory Structure

Ensure the following layout is prepared on the host machine:

```text
infra/clickhouse/
├── config/                  # ClickHouse server-side XML configurations
├── jdbc-bridge/
│   ├── config/datasources/  # JDBC datasource JSON definitions
│   └── drivers/             # (Optional) Local JDBC JAR storage
└── docker-compose.yml       # Container orchestration
```

---

## 2. Datasource Configuration (`mssql_master.json`)

Define your connection to MSSQL in `jdbc-bridge/config/datasources/mssql_master.json`. You can choose between two methods for loading the JDBC driver.

### Method A: Automated Remote URL (Recommended)
The bridge will automatically download the JAR file from the internet upon startup.

```json
{
  "mssql_master": {
    "driverUrls": [
      "https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/7.4.1.jre8/mssql-jdbc-7.4.1.jre8.jar"
    ],
    "driverClassName": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "jdbcUrl": "jdbc:sqlserver://[HOST]:[PORT];databaseName=[DB];encrypt=false;trustServerCertificate=true",
    "username": "YOUR_USER",
    "password": "YOUR_PASSWORD"
  }
}
```

### Method B: Local JAR File (For Offline Environments)
Use this if the server cannot access the internet.
1. Place the `.jar` file in `infra/clickhouse/jdbc-bridge/drivers/`.
2. Update the JSON to point to the internal container path:

```json
{
  "mssql_master": {
    "driverUrls": [
      "/app/drivers/mssql-jdbc-7.4.1.jre8.jar" 
    ],
    ...
  }
}
```

---

## 3. Inter-Container Handshake (`jdbc_bridge.xml`)

Ensure ClickHouse knows where to find the bridge by placing this in `infra/clickhouse/config/jdbc_bridge.xml`:

```xml
<clickhouse>
    <jdbc_bridge>
        <host>jdbc-bridge</host>  <!-- Matches Docker service name -->
        <port>9019</port>
    </jdbc_bridge>
</clickhouse>
```

---

## 4. Deployment (`docker-compose.yml`)

Start the services using Docker Compose. The services share a bridge network to communicate via hostnames.

```bash
docker-compose up -d
```

---

## 5. Verification

### Infrastructure Check
Check if the bridge has successfully loaded the datasource:
```bash
curl http://localhost:9019/datasource/info?active=true
```

### End-to-End SQL Test
Run this inside ClickHouse to verify the connection to MSSQL:
```sql
SELECT * FROM jdbc('mssql_master', 'SELECT 1');
```
If it returns `1`, the infrastructure is correctly set up.

---

## 6. Troubleshooting

### ⚠️ Error: `NamedDataSource [mssql_master] does not exist!` (Code: 86)
If you encounter this error during sync, check the following key points:

1. **JSON Key Name**: Open your `mssql_master.json`. The **first-level key** must be exactly `"mssql_master"`. 
   * The bridge identifies the datasource by this internal key, NOT the filename.
2. **JDBC Driver Version**: 
   * **Recommended**: Use **mssql-jdbc version 8.x** (e.g., `8.2.2.jre8`).
   * **Note**: Version 11.x has been observed to cause compatibility issues (Internal Server Error 500) in some environments.
3. **Service Restart**: Any changes to `.json` files or `.jar` files require a container restart to take effect:
   ```bash
   docker-compose restart jdbc-bridge
   ```
4. **Volume Mounting**: Ensure `infra/clickhouse/docker-compose.yml` correctly maps the local `config/datasources` directory to `/etc/clickhouse-jdbc-bridge/config/datasources` (or the configured `CONFIG_PATH`).
