#!/usr/bin/env python3
"""
驗證 ClickHouse Bronze 層是否有 Reference SQL 的 12 筆資料
"""
import clickhouse_connect

client = clickhouse_connect.get_client(
    host='REDACTED_IP',
    port=8121,
    username='default',
    password='default'
)

print("=" * 100)
print("ClickHouse Bronze 層驗證")
print("=" * 100)

# Reference TaskIds
REFERENCE_TASK_IDS = [
    '40b69867-e617-11f0-87ac-9a7dcf9ebdcc',
    '728329c9-e617-11f0-87ac-9a7dcf9ebdcc',
    '8b296ec8-e617-11f0-87ac-9a7dcf9ebdcc',
    '8bf23d5d-e617-11f0-87ac-9a7dcf9ebdcc',
    '8c7a5950-e617-11f0-87ac-9a7dcf9ebdcc',
    '98340e77-e617-11f0-87ac-9a7dcf9ebdcc',
    '9e12e535-e617-11f0-87ac-9a7dcf9ebdcc',
    'a417ba82-e617-11f0-87ac-9a7dcf9ebdcc',
    'affced2c-e617-11f0-87ac-9a7dcf9ebdcc',
    'b07a0b98-e617-11f0-87ac-9a7dcf9ebdcc',
    'b61c4e7f-e617-11f0-87ac-9a7dcf9ebdcc',
    'e64bee1e-e616-11f0-87ac-9a7dcf9ebdcc',
]

# 1. 檢查 ACT_HI_TASKINST
print("\n1. 檢查 bronze.bpm_act_hi_taskinst")
print("-" * 50)
task_ids_str = "', '".join(REFERENCE_TASK_IDS)
result = client.query(f"""
    SELECT ID_, TASK_DEF_KEY_, NAME_, ASSIGNEE_, START_TIME_, CLAIM_TIME_, END_TIME_
    FROM bronze.bpm_act_hi_taskinst FINAL
    WHERE ID_ IN ('{task_ids_str}')
""")
print(f"找到 {len(result.result_rows)} / 12 筆")
for row in result.result_rows:
    print(f"  {row[0][:36]}... | {row[1]} | {row[4]}")

# 2. 檢查 ACT_HI_VARINST (流程變數)
print("\n2. 檢查 bronze.bpm_act_hi_varinst (流程變數)")
print("-" * 50)

# 先取得這些 task 的 PROC_INST_ID_
result = client.query(f"""
    SELECT DISTINCT PROC_INST_ID_
    FROM bronze.bpm_act_hi_taskinst FINAL
    WHERE ID_ IN ('{task_ids_str}')
""")
proc_ids = [row[0] for row in result.result_rows]
print(f"對應的 PROC_INST_ID_: {len(proc_ids)} 個")

if proc_ids:
    proc_ids_str = "', '".join(proc_ids)
    
    # 檢查流程變數
    result = client.query(f"""
        SELECT NAME_, count(*) as cnt
        FROM bronze.bpm_act_hi_varinst FINAL
        WHERE PROC_INST_ID_ IN ('{proc_ids_str}')
          AND NAME_ IN ('plant', 'factory', 'lineName', 'moNumber', 'region')
        GROUP BY NAME_
    """)
    print("流程變數分布:")
    for row in result.result_rows:
        print(f"  {row[0]}: {row[1]} 筆")
    
    # 檢查 plant 和 lineName 的值
    result = client.query(f"""
        SELECT PROC_INST_ID_, NAME_, TEXT_
        FROM bronze.bpm_act_hi_varinst FINAL
        WHERE PROC_INST_ID_ IN ('{proc_ids_str}')
          AND NAME_ IN ('plant', 'lineName', 'factory')
        ORDER BY PROC_INST_ID_, NAME_
    """)
    print("\nplant/lineName/factory 值:")
    for row in result.result_rows:
        print(f"  {row[0][:20]}... | {row[1]:<10} | {row[2]}")

# 3. 檢查 ACT_HI_VARINST (Task 層級變數 - autoComplete)
print("\n3. 檢查 bronze.bpm_act_hi_varinst (Task 層級變數 - autoComplete)")
print("-" * 50)
result = client.query(f"""
    SELECT TASK_ID_, NAME_, LONG_, TEXT_
    FROM bronze.bpm_act_hi_varinst FINAL
    WHERE TASK_ID_ IN ('{task_ids_str}')
      AND NAME_ = 'autoComplete'
""")
print(f"找到 {len(result.result_rows)} 筆 autoComplete 變數")
for row in result.result_rows:
    print(f"  {row[0][:36]}... | LONG_={row[2]} | TEXT_={row[3]}")

# 4. 檢查 common_flowable_task_stats
print("\n4. 檢查 bronze.common_flowable_task_stats")
print("-" * 50)
result = client.query(f"""
    SELECT TaskId, TaskStatus, TaskBypass, Plant, Line, Factory, TaskCreateTime
    FROM bronze.common_flowable_task_stats FINAL
    WHERE TaskId IN ('{task_ids_str}')
""")
print(f"找到 {len(result.result_rows)} / 12 筆")
for row in result.result_rows:
    print(f"  {row[0][:36]}... | {row[1]:<6} | {row[2]} | {row[3]} | {row[4]} | {row[5]}")

# 5. 用等價 SQL 查詢 ClickHouse
print("\n" + "=" * 100)
print("5. 用等價 SQL 查詢 ClickHouse Bronze 層")
print("=" * 100)

# 先建立 varinst pivot CTE
result = client.query("""
WITH varinst_pivot AS (
    SELECT 
        PROC_INST_ID_,
        MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS plant,
        MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS factory,
        MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS lineName
    FROM bronze.bpm_act_hi_varinst FINAL
    WHERE NAME_ IN ('plant', 'factory', 'lineName')
    GROUP BY PROC_INST_ID_
),
task_bypass AS (
    SELECT 
        TASK_ID_,
        MAX(CASE WHEN LONG_ = 1 THEN 'Y' ELSE 'N' END) AS taskBypass
    FROM bronze.bpm_act_hi_varinst FINAL
    WHERE NAME_ = 'autoComplete'
    GROUP BY TASK_ID_
)
SELECT 
    hti.ID_ AS taskId,
    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
        WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
        ELSE 'TODO'
    END AS taskStatus,
    COALESCE(tb.taskBypass, 'N') AS taskBypass,
    vp.plant,
    vp.lineName AS line,
    vp.factory,
    hti.START_TIME_ AS taskCreateTime
FROM bronze.bpm_act_hi_taskinst hti FINAL
LEFT JOIN varinst_pivot vp ON hti.PROC_INST_ID_ = vp.PROC_INST_ID_
LEFT JOIN task_bypass tb ON hti.ID_ = tb.TASK_ID_
WHERE toDate(hti.START_TIME_) = '2025-12-31'
  AND COALESCE(tb.taskBypass, 'N') = 'N'
  AND vp.plant = 'WJ2'
  AND vp.lineName = 'E5'
""")

print(f"\n查詢結果: {len(result.result_rows)} 筆")
print(f"\n{'taskId':<40} {'status':<8} {'bypass':<6} {'plant':<6} {'line':<6} {'factory':<8}")
print("-" * 90)
for row in result.result_rows:
    print(f"{row[0]:<40} {row[1]:<8} {row[2]:<6} {str(row[3]):<6} {str(row[4]):<6} {str(row[5]):<8}")

# 狀態統計
if result.result_rows:
    status_counts = {}
    for row in result.result_rows:
        status = row[1]
        status_counts[status] = status_counts.get(status, 0) + 1
    print("\n狀態統計:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

print("\n預期結果: 12 筆 (TODO=8, DOING=2, DONE=2)")
