#!/usr/bin/env python3
"""
測試：使用 QAS 相同的時間篩選邏輯 (START_TIME OR CLAIM_TIME OR END_TIME)
"""
import clickhouse_connect

client = clickhouse_connect.get_client(
    host='10.136.218.207',
    port=8121,
    username='default',
    password='default',
    database='default',
    send_receive_timeout=600
)

print("=" * 60)
print("測試時間篩選邏輯對齊 QAS_L5_task.sql")
print("篩選條件: 2025-12-25, WJ2, NBU, E5")
print("=" * 60)

# 1. 目前 Gold 層結果 (只用 task_create_date)
print("\n【方式 1】目前 Gold 層邏輯 - 只看 task_start_date (建立日期)")
r1 = client.query("""
    SELECT 
        count() AS total,
        countIf(task_status = 'TODO') AS todo,
        countIf(task_status = 'DOING') AS doing,
        countIf(task_status = 'DONE') AS done
    FROM silver.mv_fact_task_vx FINAL
    WHERE task_start_date = '2025-12-25'
      AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND is_excluded = 0
""")
print(f"  Total: {r1.result_rows[0][0]}, TODO: {r1.result_rows[0][1]}, DOING: {r1.result_rows[0][2]}, DONE: {r1.result_rows[0][3]}")

# 2. 模擬 QAS 邏輯 (START_TIME OR CLAIM_TIME OR END_TIME)
print("\n【方式 2】QAS 邏輯 - START_TIME OR CLAIM_TIME OR END_TIME")
r2 = client.query("""
    SELECT 
        count() AS total,
        countIf(task_status = 'TODO') AS todo,
        countIf(task_status = 'DOING') AS doing,
        countIf(task_status = 'DONE') AS done
    FROM silver.mv_fact_task_vx FINAL
    WHERE (task_start_date = '2025-12-25' 
           OR task_claim_date = '2025-12-25' 
           OR task_end_date = '2025-12-25')
      AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND is_excluded = 0
""")
print(f"  Total: {r2.result_rows[0][0]}, TODO: {r2.result_rows[0][1]}, DOING: {r2.result_rows[0][2]}, DONE: {r2.result_rows[0][3]}")

# 3. 不排除 bypass 的情況
print("\n【方式 3】QAS 邏輯 + 不排除 bypass")
r3 = client.query("""
    SELECT 
        count() AS total,
        countIf(task_status = 'TODO') AS todo,
        countIf(task_status = 'DOING') AS doing,
        countIf(task_status = 'DONE') AS done
    FROM silver.mv_fact_task_vx FINAL
    WHERE (task_start_date = '2025-12-25' 
           OR task_claim_date = '2025-12-25' 
           OR task_end_date = '2025-12-25')
      AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
""")
print(f"  Total: {r3.result_rows[0][0]}, TODO: {r3.result_rows[0][1]}, DOING: {r3.result_rows[0][2]}, DONE: {r3.result_rows[0][3]}")

print("\n" + "=" * 60)
print("比對目標: QAS SQL 結果 = 198 筆 (全部 DONE, taskBypass=N 約 193 筆)")
print("=" * 60)
