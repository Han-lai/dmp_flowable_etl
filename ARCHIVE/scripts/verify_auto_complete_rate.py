import clickhouse_connect

client = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

print("=== 事件自動完成率 驗證 ===")
print("定義: 自動完成任務數 / 總完成任務數 * 100%")
print()

# 1. 從 V_HI_BIZ_EVENT_INFO 計算整體自動完成率
print("--- 方法1: 從 V_HI_BIZ_EVENT_INFO 彙總 ---")
result = client.query("""
SELECT 
    sum(TASK_DONE_CNT) AS done_cnt,
    sum(TASK_AUTOCOMPLETE_CNT) AS auto_cnt,
    sum(TASK_DONE_CNT) + sum(TASK_AUTOCOMPLETE_CNT) AS total_completed,
    round(sum(TASK_AUTOCOMPLETE_CNT) * 100.0 / (sum(TASK_DONE_CNT) + sum(TASK_AUTOCOMPLETE_CNT)), 2) AS auto_rate
FROM silver.V_HI_BIZ_EVENT_INFO
""")
row = result.result_rows[0]
print(f"手動完成 (DONE): {row[0]}")
print(f"自動完成 (DONE_AUTO): {row[1]}")
print(f"總完成數: {row[2]}")
print(f"自動完成率: {row[3]}%")

# 2. 從 V_HI_PROC_TASK_NODE 直接計算
print("\n--- 方法2: 從 V_HI_PROC_TASK_NODE 直接計算 ---")
result2 = client.query("""
SELECT 
    countIf(TASK_STATUS = 'DONE') AS done_cnt,
    countIf(TASK_STATUS = 'DONE_AUTO') AS auto_cnt,
    countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')) AS total_completed,
    round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) AS auto_rate
FROM silver.V_HI_PROC_TASK_NODE
""")
row2 = result2.result_rows[0]
print(f"手動完成 (DONE): {row2[0]}")
print(f"自動完成 (DONE_AUTO): {row2[1]}")
print(f"總完成數: {row2[2]}")
print(f"自動完成率: {row2[3]}%")

# 3. 依流程定義分組的自動完成率
print("\n--- 依流程定義分組的自動完成率 (Top 10) ---")
result3 = client.query("""
SELECT 
    PROC_DEF_NAME,
    countIf(TASK_STATUS = 'DONE') AS done_cnt,
    countIf(TASK_STATUS = 'DONE_AUTO') AS auto_cnt,
    countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')) AS total,
    round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) AS auto_rate
FROM silver.V_HI_PROC_TASK_NODE
WHERE TASK_STATUS IN ('DONE', 'DONE_AUTO')
GROUP BY PROC_DEF_NAME
HAVING total >= 10
ORDER BY total DESC
LIMIT 10
""")
print(f"{'流程名稱':<40} | {'DONE':>6} | {'AUTO':>6} | {'總數':>6} | {'自動率':>6}")
print("-" * 75)
for row in result3.result_rows:
    name = (row[0] or '未知')[:38]
    print(f"{name:<40} | {row[1]:>6} | {row[2]:>6} | {row[3]:>6} | {row[4]:>5}%")

# 4. 依業務事件計算自動完成率
print("\n--- 依業務事件的自動完成率分布 ---")
result4 = client.query("""
SELECT 
    CASE 
        WHEN auto_rate = 0 THEN '0% (全手動)'
        WHEN auto_rate > 0 AND auto_rate < 50 THEN '1-49%'
        WHEN auto_rate >= 50 AND auto_rate < 100 THEN '50-99%'
        WHEN auto_rate = 100 THEN '100% (全自動)'
        ELSE '無完成任務'
    END AS rate_range,
    count(*) AS event_cnt
FROM (
    SELECT 
        BIZ_EVENT_KEY,
        TASK_DONE_CNT + TASK_AUTOCOMPLETE_CNT AS total_completed,
        if(TASK_DONE_CNT + TASK_AUTOCOMPLETE_CNT > 0, 
           round(TASK_AUTOCOMPLETE_CNT * 100.0 / (TASK_DONE_CNT + TASK_AUTOCOMPLETE_CNT), 0), 
           -1) AS auto_rate
    FROM silver.V_HI_BIZ_EVENT_INFO
)
GROUP BY rate_range
ORDER BY rate_range
""")
print(f"{'自動完成率區間':<20} | {'事件數':>10}")
print("-" * 35)
for row in result4.result_rows:
    print(f"{row[0]:<20} | {row[1]:>10}")
