# MSSQL Mock Server

MVP 測試用 MSSQL，包含 Flowable 和 DMP 模擬資料表。

## 連線資訊

| 項目 | 值 |
|------|-----|
| Host | localhost |
| Port | 1433 |
| User | sa |
| Password | YourStrong@Passw0rd |

## Database

- `APP_SRV_BPM` - Flowable 流程資料（5 張表）
- `APP_SRV_COMMON` - DMP 組織人員資料（11 張表）

## 啟動

```bash
cd docker/mssql-mock
docker-compose up -d
```

## 初始化

⚠️ MSSQL Docker 不會自動執行 init SQL，啟動後需手動執行：

```bash
# 等待 MSSQL 啟動（約 30 秒）
sleep 30

# 執行初始化 SQL
docker exec -it mssql-mock /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'YourStrong@Passw0rd' -C \
  -i /docker-entrypoint-initdb.d/01_create_databases.sql

docker exec -it mssql-mock /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'YourStrong@Passw0rd' -C \
  -i /docker-entrypoint-initdb.d/02_create_bpm_tables.sql

docker exec -it mssql-mock /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'YourStrong@Passw0rd' -C \
  -i /docker-entrypoint-initdb.d/03_create_common_tables.sql
```

## 表說明

### APP_SRV_BPM（Flowable）

| 表名 | 說明 |
|------|------|
| ACT_HI_PROCINST | 流程實例歷史 |
| ACT_HI_TASKINST | 任務實例歷史 |
| ACT_HI_IDENTITYLINK | 任務參與者歷史 |
| ACT_HI_VARINST | 流程變數歷史 |
| ACT_RE_PROCDEF | 流程定義 |

### APP_SRV_COMMON（DMP）

| 表名 | 說明 |
|------|------|
| FlowableTaskStats | 任務統計彙總 |
| HR_Employee | 員工主檔 |
| ProcessRoleUserMapping | 角色-員工對應 |
| ProcessRoleGroup | 角色群組定義 |
| ProcessRoleGroupMapping | 角色群組對應 |
| EmpNodeRoleMapping | 員工-節點角色 |
| EmpOrgInfoMapping | 員工-組織對應 |
| EmpUserGroupMapping | 員工-群組對應 |
| UserGroup | 使用者群組定義 |
| DMPFunctionConfig | 功能設定 |
| DMPFunctionClientMapping | 客戶端對應 |
