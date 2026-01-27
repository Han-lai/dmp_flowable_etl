#!/usr/bin/env python3
"""
對帳驗證：ClickHouse vs MSSQL Reference SQL
"""
import pymssql
import clickhouse_connect

print("=" * 100)
print("對帳驗證：ClickHouse vs MSSQL")
print("條件: date=2025-12-31, taskBypass='N', plant='WJ2', line='E5'")
print("=" * 100)

# MSSQL 連線
mssql_conn = pymssql.connect(
    server='twtpesqldv2.delta.corp',
    port='1433',
    user='DMP_APP_SRV',
    password='APP@DB#01',
    database='APP_SRV_BPM'
)
mssql_cursor = mssql_conn.cursor()

# ClickHouse 連線
ch_client = clickhouse_connect.get_client(
    host='10.136.218.207',
    port=8121,
    username='default',
    password='default'
)

# ============================================
# 1. MSSQL Reference SQL
# ============================================
print("\n" + "=" * 50)
print("1. MSSQL Reference SQL 結果")
print("=" * 50)

mssql_cursor.execute("""
SELECT * FROM (
SELECT
    hti.ID_ AS taskId,
    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
        WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
        ELSE 'TODO'
    END AS taskStatus,
    CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END AS taskBypass,
    var_plant.TEXT_ AS plant,
    var_lineName.TEXT_ AS line,
    var_factory.TEXT_ AS factory,
    CONVERT(VARCHAR, hti.START_TIME_, 120) AS taskCreateTime
FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
) AS t
WHERE t.taskCreateTime BETWEEN '2025-12-31 00:00:00' AND '2025-12-31 23:59:59'
  AND taskBypass='N' 
  AND plant='WJ2' 
  AND line='E5'
ORDER BY taskId
""")

mssql_rows = mssql_cursor.fetchall()
mssql_task_ids = set()
mssql_status_counts = {}

print(f"\n總筆數: {len(mssql_rows)}")
print(f"\n{'taskId':<40} {'status':<8} {'bypass':<6} {'plant':<6} {'line':<6}")
print("-" * 80)
for row in mssql_rows:
    task_id = row[0]
    status = row[1]
    mssql_task_ids.add(task_id)
    mssql_status_counts[status] = mssql_status_counts.get(status, 0) + 1
    print(f"{task_id:<40} {status:<8} {row[2]:<6} {row[3]:<6} {row[4]:<6}")

print("\n狀態統計:")
for status, count in sorted(mssql_status_counts.items()):
    print(f"  {status}: {count}")

# ============================================
# 2. ClickHouse Silver 層結果
# ============================================
print("\n" + "=" * 50)
print("2. ClickHouse Silver 層結果")
print("=" * 50)

ch_result = ch_client.query("""
SELECT 
    task_id,
    task_status,
    task_bypass,
    plant,
    line
FROM silver.task_detail_wide FINAL
WHERE task_create_date = '2025-12-31'
  AND task_bypass = 'N'
  AND plant = 'WJ2'
  AND line = 'E5'
ORDER BY task_id
""")

ch_task_ids = set()
ch_status_counts = {}

print(f"\n總筆數: {len(ch_result.result_rows)}")
print(f"\n{'taskId':<40} {'status':<8} {'bypass':<6} {'plant':<6} {'line':<6}")
print("-" * 80)
for row in ch_result.result_rows:
    task_id = row[0]
    status = row[1]
    ch_task_ids.add(task_id)
    ch_status_counts[status] = ch_status_counts.get(status, 0) + 1
    print(f"{task_id:<40} {status:<8} {row[2]:<6} {str(row[3]):<6} {str(row[4]):<6}")

print("\n狀態統計:")
for status, count in sorted(ch_status_counts.items()):
    print(f"  {status}: {count}")

# ============================================
# 3. 對帳結果
# ============================================
print("\n" + "=" * 100)
print("3. 對帳結果")
print("=" * 100)

# 筆數比較
print(f"\n筆數比較:")
print(f"  MSSQL:      {len(mssql_rows)}")
print(f"  ClickHouse: {len(ch_result.result_rows)}")
print(f"  差異:       {len(mssql_rows) - len(ch_result.result_rows)}")

# TaskId 比較
only_in_mssql = mssql_task_ids - ch_task_ids
only_in_ch = ch_task_ids - mssql_task_ids

print(f"\nTaskId 比較:")
print(f"  只在 MSSQL:      {len(only_in_mssql)}")
print(f"  只在 ClickHouse: {len(only_in_ch)}")

if only_in_mssql:
    print(f"  MSSQL 獨有: {only_in_mssql}")
if only_in_ch:
    print(f"  ClickHouse 獨有: {only_in_ch}")

# 狀態分布比較
print(f"\n狀態分布比較:")
all_statuses = set(mssql_status_counts.keys()) | set(ch_status_counts.keys())
for status in sorted(all_statuses):
    mssql_cnt = mssql_status_counts.get(status, 0)
    ch_cnt = ch_status_counts.get(status, 0)
    match = "✓" if mssql_cnt == ch_cnt else "✗"
    print(f"  {status}: MSSQL={mssql_cnt}, ClickHouse={ch_cnt} {match}")

# 最終結論
print("\n" + "=" * 100)
if len(mssql_rows) == len(ch_result.result_rows) and not only_in_mssql and not only_in_ch:
    print("✅ 對帳通過！MSSQL 與 ClickHouse 結果完全一致")
else:
    print("⚠️ 對帳失敗！請檢查差異")
print("=" * 100)

mssql_conn.close()
