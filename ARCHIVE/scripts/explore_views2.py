import clickhouse_connect

# 你的環境
client = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

# 檢查是否有符合 DONE_AUTO 條件的資料
# DONE_AUTO = ASSIGNEE IS NOT NULL AND CLAIM_TIME IS NULL AND END_TIME IS NOT NULL
print("=== 檢查 DONE_AUTO 條件的資料 ===")
query = """
SELECT 
    multiIf(
        DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != '', 'TERMINATED',
        ASSIGNEE_ IS NULL AND END_TIME_ IS NULL, 'TODO',
        ASSIGNEE_ IS NOT NULL AND END_TIME_ IS NULL, 'DOING',
        ASSIGNEE_ IS NOT NULL AND CLAIM_TIME_ IS NULL AND END_TIME_ IS NOT NULL, 'DONE_AUTO',
        END_TIME_ IS NOT NULL, 'DONE',
        'UNKNOWN'
    ) AS task_state,
    count(*) AS cnt
FROM bronze.bpm_act_hi_taskinst
GROUP BY task_state
ORDER BY cnt DESC
"""
result = client.query(query)
print("task_state | count")
print("-" * 30)
for row in result.result_rows:
    print(f"{row[0]:15} | {row[1]}")

# 對比目前 View 的 TASK_STATUS
print("\n=== 目前 View 的 TASK_STATUS 分布 ===")
query2 = """
SELECT TASK_STATUS, count(*) AS cnt
FROM silver.V_HI_PROC_TASK_NODE
GROUP BY TASK_STATUS
ORDER BY cnt DESC
"""
result2 = client.query(query2)
print("TASK_STATUS | count")
print("-" * 30)
for row in result2.result_rows:
    print(f"{row[0]:15} | {row[1]}")
