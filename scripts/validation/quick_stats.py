
import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

filters = "plant='WJ2' AND factory='NBU' AND line='E5' AND toDate(snapshot_date)='2025-12-25'"

print("--- Quick Stats Check ---")

# 1. Gold Count (Base)
q1 = f"SELECT count() FROM gold.rmv_l5_task_completion WHERE {filters}"
c1 = client.command(q1)
print(f"Gold Count (Standard): {c1}")

# 2. Gold Count (FINAL)
q2 = f"SELECT count() FROM gold.rmv_l5_task_completion FINAL WHERE {filters}"
c2 = client.command(q2)
print(f"Gold Count (FINAL):    {c2}")

# 3. Gold Sum Total Task (Maybe the user looked at sum(total_task)?)
q3 = f"SELECT sum(total_task) FROM gold.rmv_l5_task_completion WHERE {filters}"
c3 = client.command(q3)
print(f"Gold Sum(total_task):  {c3}")

# 4. Silver Expanded Count (Raw reconstruction)
q4 = f"""
SELECT count() 
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
WHERE {filters} AND is_excluded=0
"""
c4 = client.command(q4)
print(f"Silver Reconstructed:  {c4}")

print("-------------------------")
