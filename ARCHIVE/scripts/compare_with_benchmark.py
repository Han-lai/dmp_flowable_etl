import clickhouse_connect

# 你的環境
my_client = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

# 參考環境 (benchmark)
ref_client = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me'
)

print("=== 以參考環境為 Benchmark 比較 View / RMV 資料正確性 ===\n")
print("參考環境: flowable_analytics (gold_proc_task_node_rmv, gold_procinst_node_rmv)")
print("你的環境: silver (V_*, RMV_*)")
print("注意: 參考環境使用 node_state 欄位，你的環境使用 TASK_STATUS 欄位\n")

# 比較項目：(名稱, 參考環境SQL, View SQL, RMV SQL)
# 參考環境欄位: node_state (DONE, DOING, TODO, DONE_AUTO, TERMINATE, TERMINATED)
# 你的環境欄位: TASK_STATUS (DONE, DOING, TODO, DONE_AUTO, CANCELLED)
COMPARISONS = [
    ("總筆數 - TASK_NODE", 
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE"),
    ("總筆數 - PROCINST_NODE",
     "SELECT count(*) FROM flowable_analytics.gold_procinst_node_rmv",
     "SELECT count(*) FROM silver.V_HI_PROCINST_NODE",
     "SELECT count(*) FROM silver.RMV_HI_PROCINST_NODE"),
    ("在途任務數 (TODO+DOING)",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_state IN ('TODO', 'DOING')",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')"),
    ("DONE 任務數",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_state = 'DONE'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'"),
    ("DONE_AUTO 任務數",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_state = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'"),
    ("CANCELLED (Benchmark: TERMINATE+TERMINATED)",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_state IN ('TERMINATE', 'TERMINATED')",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'"),
    ("自動完成率 (%)",
     "SELECT round(countIf(node_state = 'DONE_AUTO') * 100.0 / countIf(node_state IN ('DONE', 'DONE_AUTO')), 2) FROM flowable_analytics.gold_proc_task_node_rmv",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.RMV_HI_PROC_TASK_NODE"),
]

print(f"{'指標':<35} | {'Benchmark':>12} | {'View':>12} | {'RMV':>12} | {'View':>6} | {'RMV':>6}")
print("-" * 100)

all_view_match = True
all_rmv_match = True

for name, ref_sql, view_sql, rmv_sql in COMPARISONS:
    try:
        ref_result = ref_client.query(ref_sql).result_rows[0][0]
    except Exception as e:
        ref_result = "ERR"
    
    try:
        view_result = my_client.query(view_sql).result_rows[0][0]
    except Exception as e:
        view_result = "ERR"
    
    try:
        rmv_result = my_client.query(rmv_sql).result_rows[0][0]
    except Exception as e:
        rmv_result = "ERR"
    
    view_match = "✅" if ref_result == view_result else "❌"
    rmv_match = "✅" if ref_result == rmv_result else "❌"
    
    if ref_result != view_result:
        all_view_match = False
    if ref_result != rmv_result:
        all_rmv_match = False
    
    print(f"{name:<35} | {ref_result:>12} | {view_result:>12} | {rmv_result:>12} | {view_match:>6} | {rmv_match:>6}")

print("-" * 100)

# 總結
print("\n=== 總結 ===")
print(f"View 與 Benchmark 一致: {'✅ 全部一致' if all_view_match else '❌ 有差異'}")
print(f"RMV 與 Benchmark 一致: {'✅ 全部一致' if all_rmv_match else '❌ 有差異'}")

# node_state / TASK_STATUS 分布比較
print("\n=== 狀態分布比較 ===")
print("Benchmark 使用 node_state，你的環境使用 TASK_STATUS")
print(f"{'狀態':<20} | {'Benchmark':>12} | {'View':>12} | {'RMV':>12}")
print("-" * 65)

ref_dist = ref_client.query("SELECT node_state, count(*) FROM flowable_analytics.gold_proc_task_node_rmv GROUP BY node_state ORDER BY node_state").result_rows
view_dist = my_client.query("SELECT TASK_STATUS, count(*) FROM silver.V_HI_PROC_TASK_NODE GROUP BY TASK_STATUS ORDER BY TASK_STATUS").result_rows
rmv_dist = my_client.query("SELECT TASK_STATUS, count(*) FROM silver.RMV_HI_PROC_TASK_NODE GROUP BY TASK_STATUS ORDER BY TASK_STATUS").result_rows

ref_dict = {row[0]: row[1] for row in ref_dist}
view_dict = {row[0]: row[1] for row in view_dist}
rmv_dict = {row[0]: row[1] for row in rmv_dist}

# 狀態對應
status_mapping = {
    'TODO': 'TODO',
    'DOING': 'DOING', 
    'DONE': 'DONE',
    'DONE_AUTO': 'DONE_AUTO',
    'CANCELLED': 'TERMINATE+TERMINATED',
}

print("\n--- Benchmark (node_state) ---")
for status, count in sorted(ref_dict.items()):
    print(f"{status:<20} | {count:>12}")

print("\n--- View (TASK_STATUS) ---")
for status, count in sorted(view_dict.items()):
    print(f"{status:<20} | {count:>12}")

print("\n--- RMV (TASK_STATUS) ---")
for status, count in sorted(rmv_dict.items()):
    print(f"{status:<20} | {count:>12}")
