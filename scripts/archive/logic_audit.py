"""
計算邏輯一致性審核 (Logic Equivalence Check)
比對 Benchmark vs View vs RMV 的語意等價性
僅讀取 Benchmark，不做任何修改
"""
import clickhouse_connect

# Benchmark (READ ONLY)
benchmark = clickhouse_connect.get_client(
    host='10.136.218.207', port=8124, 
    username='ch_user', password='ch_strong_password_change_me'
)

# 我的環境
my_env = clickhouse_connect.get_client(
    host='10.136.218.207', port=8121, 
    username='default', password='default'
)

print("=" * 80)
print("計算邏輯一致性審核 (Logic Equivalence Check)")
print("=" * 80)

# ============================================
# Part 1: Benchmark 結構查詢 (READ ONLY)
# ============================================
print("\n【Part 1】Benchmark 結構 (READ ONLY)")
print("-" * 60)

print("\n🔹 gold_proc_task_node_rmv 欄位:")
result = benchmark.query("""
SELECT name, type FROM system.columns 
WHERE database = 'flowable_analytics' AND table = 'gold_proc_task_node_rmv'
ORDER BY position
""")
bm_task_cols = {}
for row in result.result_rows:
    bm_task_cols[row[0]] = row[1]
    print(f"   {row[0]}: {row[1]}")

print("\n🔹 gold_procinst_node_rmv 欄位:")
result = benchmark.query("""
SELECT name, type FROM system.columns 
WHERE database = 'flowable_analytics' AND table = 'gold_procinst_node_rmv'
ORDER BY position
""")
bm_proc_cols = {}
for row in result.result_rows:
    bm_proc_cols[row[0]] = row[1]
    print(f"   {row[0]}: {row[1]}")

# ============================================
# Part 2: 我的環境結構
# ============================================
print("\n【Part 2】我的環境結構")
print("-" * 60)

print("\n🔹 V_HI_PROC_TASK_NODE 欄位:")
result = my_env.query("""
SELECT name, type FROM system.columns 
WHERE database = 'silver' AND table = 'V_HI_PROC_TASK_NODE'
ORDER BY position
""")
my_task_cols = {}
for row in result.result_rows:
    my_task_cols[row[0]] = row[1]
    print(f"   {row[0]}: {row[1]}")

print("\n🔹 V_HI_PROCINST_NODE 欄位:")
result = my_env.query("""
SELECT name, type FROM system.columns 
WHERE database = 'silver' AND table = 'V_HI_PROCINST_NODE'
ORDER BY position
""")
my_proc_cols = {}
for row in result.result_rows:
    my_proc_cols[row[0]] = row[1]
    print(f"   {row[0]}: {row[1]}")

# ============================================
# Part 3: 欄位對應分析
# ============================================
print("\n【Part 3】欄位對應分析")
print("-" * 60)

def analyze_columns(bm_cols, my_cols, name):
    print(f"\n🔹 {name}")
    common = set(bm_cols.keys()) & set(my_cols.keys())
    only_bm = set(bm_cols.keys()) - set(my_cols.keys())
    only_my = set(my_cols.keys()) - set(bm_cols.keys())
    
    print(f"   共同欄位: {len(common)}")
    print(f"   僅 Benchmark 有: {len(only_bm)}")
    print(f"   僅我的環境有: {len(only_my)}")
    
    if only_bm:
        print(f"\n   ⚠️ Benchmark 有但我沒有:")
        for col in sorted(only_bm):
            print(f"      - {col}")
    
    if only_my:
        print(f"\n   ℹ️ 我有但 Benchmark 沒有:")
        for col in sorted(only_my):
            print(f"      - {col}")
    
    return common, only_bm, only_my

analyze_columns(bm_task_cols, my_task_cols, "TASK_NODE 欄位比較")
analyze_columns(bm_proc_cols, my_proc_cols, "PROCINST_NODE 欄位比較")

# ============================================
# Part 4: 狀態欄位語意比較
# ============================================
print("\n【Part 4】狀態欄位語意比較")
print("-" * 60)

# Benchmark 狀態分布
print("\n🔹 Benchmark node_state 分布:")
result = benchmark.query("""
SELECT node_state, count(*) as cnt 
FROM flowable_analytics.gold_proc_task_node_rmv 
GROUP BY node_state ORDER BY node_state
""")
for row in result.result_rows:
    print(f"   {row[0]}: {row[1]}")

# 我的環境狀態分布
print("\n🔹 我的 TASK_STATUS 分布 (View):")
result = my_env.query("""
SELECT TASK_STATUS, count(*) as cnt 
FROM silver.V_HI_PROC_TASK_NODE 
GROUP BY TASK_STATUS ORDER BY TASK_STATUS
""")
for row in result.result_rows:
    print(f"   {row[0]}: {row[1]}")

print("\n🔹 我的 TASK_STATUS 分布 (RMV):")
result = my_env.query("""
SELECT TASK_STATUS, count(*) as cnt 
FROM silver.RMV_HI_PROC_TASK_NODE FINAL
GROUP BY TASK_STATUS ORDER BY TASK_STATUS
""")
for row in result.result_rows:
    print(f"   {row[0]}: {row[1]}")

# ============================================
# Part 5: 關鍵指標邏輯比較
# ============================================
print("\n【Part 5】關鍵指標邏輯比較")
print("-" * 60)

metrics = [
    ("在途任務 (TODO+DOING)",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_state IN ('TODO', 'DOING')",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE FINAL WHERE TASK_STATUS IN ('TODO', 'DOING')"),
    ("已完成任務 (DONE)",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_state = 'DONE'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE FINAL WHERE TASK_STATUS = 'DONE'"),
    ("自動完成 (DONE_AUTO)",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_state = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE FINAL WHERE TASK_STATUS = 'DONE_AUTO'"),
    ("取消任務 (CANCELLED vs TERMINATE)",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_state IN ('TERMINATE', 'TERMINATED')",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE FINAL WHERE TASK_STATUS = 'CANCELLED'"),
    ("自動完成率 (%)",
     "SELECT round(countIf(node_state = 'DONE_AUTO') * 100.0 / countIf(node_state IN ('DONE', 'DONE_AUTO')), 2) FROM flowable_analytics.gold_proc_task_node_rmv",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.RMV_HI_PROC_TASK_NODE FINAL"),
]

print(f"\n{'指標':<30} | {'Benchmark':>12} | {'View':>12} | {'RMV':>12} | View一致 | RMV一致")
print("-" * 100)

for name, bm_sql, view_sql, rmv_sql in metrics:
    bm_val = benchmark.query(bm_sql).result_rows[0][0]
    view_val = my_env.query(view_sql).result_rows[0][0]
    rmv_val = my_env.query(rmv_sql).result_rows[0][0]
    
    view_match = "✅" if bm_val == view_val else "❌"
    rmv_match = "✅" if bm_val == rmv_val else "❌"
    
    print(f"{name:<30} | {bm_val:>12} | {view_val:>12} | {rmv_val:>12} | {view_match:>8} | {rmv_match:>8}")

# ============================================
# Part 6: View vs RMV 一致性
# ============================================
print("\n【Part 6】View vs RMV 一致性")
print("-" * 60)

view_rmv_checks = [
    ("TASK_NODE 筆數",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE FINAL"),
    ("PROCINST_NODE 筆數",
     "SELECT count(*) FROM silver.V_HI_PROCINST_NODE",
     "SELECT count(*) FROM silver.RMV_HI_PROCINST_NODE FINAL"),
]

for name, view_sql, rmv_sql in view_rmv_checks:
    view_val = my_env.query(view_sql).result_rows[0][0]
    rmv_val = my_env.query(rmv_sql).result_rows[0][0]
    match = "✅" if view_val == rmv_val else "❌"
    print(f"{name}: View={view_val}, RMV={rmv_val} {match}")

print("\n" + "=" * 80)
print("審核完成")
print("=" * 80)
