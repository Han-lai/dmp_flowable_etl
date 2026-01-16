import clickhouse_connect

client = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

print("=== View vs RMV 資料正確性比較 ===\n")

COMPARISONS = [
    ("總筆數 - TASK_NODE", 
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE"),
    ("總筆數 - PROCINST_NODE",
     "SELECT count(*) FROM silver.V_HI_PROCINST_NODE",
     "SELECT count(*) FROM silver.RMV_HI_PROCINST_NODE"),
    ("總筆數 - BIZ_EVENT_INFO",
     "SELECT count(*) FROM silver.V_HI_BIZ_EVENT_INFO",
     "SELECT count(*) FROM silver.RMV_HI_BIZ_EVENT_INFO"),
    ("在途任務數",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')"),
    ("DONE 任務數",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'"),
    ("DONE_AUTO 任務數",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'"),
    ("CANCELLED 任務數",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'"),
    ("在途業務事件數",
     "SELECT count(*) FROM silver.V_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NULL",
     "SELECT count(*) FROM silver.RMV_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NULL"),
    ("自動完成率",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.RMV_HI_PROC_TASK_NODE"),
]

print(f"{'指標':<25} | {'View':>12} | {'RMV':>12} | {'一致'}")
print("-" * 65)

all_match = True
for name, view_sql, rmv_sql in COMPARISONS:
    view_result = client.query(view_sql).result_rows[0][0]
    rmv_result = client.query(rmv_sql).result_rows[0][0]
    match = "✅" if view_result == rmv_result else "❌"
    if view_result != rmv_result:
        all_match = False
    print(f"{name:<25} | {view_result:>12} | {rmv_result:>12} | {match}")

print("-" * 65)
if all_match:
    print("✅ 所有指標資料一致")
else:
    print("❌ 有指標資料不一致")
