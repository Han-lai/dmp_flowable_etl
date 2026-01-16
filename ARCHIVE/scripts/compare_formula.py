import clickhouse_connect

my_client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
ref_client = clickhouse_connect.get_client(host='REDACTED_IP', port=8124, username='ch_user', password='ch_strong_password_change_me')

print('=' * 80)
print('以參考環境為 Benchmark 比較計算公式與欄位選擇')
print('=' * 80)

print()
print('【1. TASK_STATUS 計算邏輯比較】')
print('-' * 60)
print('參考環境 (task_state):')
print('  DELETE_REASON_ IS NOT NULL → TERMINATED')
print('  ASSIGNEE_ IS NULL AND END_TIME_ IS NULL → TODO')
print('  ASSIGNEE_ IS NOT NULL AND END_TIME_ IS NULL → DOING')
print('  ASSIGNEE_ IS NOT NULL AND CLAIM_TIME_ IS NULL AND END_TIME_ IS NOT NULL → DONE_AUTO')
print('  其他 → DONE')
print()
print('你的環境 (TASK_STATUS):')
print('  DELETE_REASON_ IS NOT NULL → CANCELLED')
print('  ASSIGNEE_ IS NULL AND END_TIME_ IS NULL → TODO')
print('  ASSIGNEE_ IS NOT NULL AND END_TIME_ IS NULL → DOING')
print('  ASSIGNEE_ IS NOT NULL AND CLAIM_TIME_ IS NULL AND END_TIME_ IS NOT NULL → DONE_AUTO')
print('  其他 → DONE')
print()
print('✅ 結論: 邏輯完全相同，只是狀態名稱不同 (TERMINATED vs CANCELLED)')

print()
print('【2. 參考環境的 TERMINATE 來源】')
print('-' * 60)
print('gold_proc_task_node_rmv 是 UNION ALL 兩個來源:')
print('  1. gold_procinst_node_rmv (流程層) - node_type = PROC')
print('     proc_state: TERMINATE / DOING / DONE')
print('  2. silver_enriched_taskinst (任務層) - node_type = TASK')
print('     task_state: TERMINATED / TODO / DOING / DONE_AUTO / DONE')
print()
print('所以:')
print('  - TERMINATE (1,510 筆) = 流程被終止')
print('  - TERMINATED (3,094 筆) = 任務被終止')
print()
print('你的環境只有任務層，沒有流程層的 PROC 記錄')

print()
print('【3. 參考環境的過濾條件】')
print('-' * 60)
print('參考環境在 silver_enriched_taskinst 有過濾:')
print("  WHERE TASK_DEF_KEY_ NOT LIKE 'E%'")
print("    AND TASK_DEF_KEY_ NOT LIKE 'C%'")
print("    AND (proc_mo_number IS NULL OR (proc_mo_number NOT LIKE 'Q%' AND proc_mo_number NOT LIKE 'R%'))")
print()

# 計算過濾影響
total = my_client.query('SELECT count(*) FROM bronze.bpm_act_hi_taskinst').result_rows[0][0]
filtered_e = my_client.query("SELECT count(*) FROM bronze.bpm_act_hi_taskinst WHERE TASK_DEF_KEY_ LIKE 'E%'").result_rows[0][0]
filtered_c = my_client.query("SELECT count(*) FROM bronze.bpm_act_hi_taskinst WHERE TASK_DEF_KEY_ LIKE 'C%'").result_rows[0][0]
after_filter = total - filtered_e - filtered_c

print(f'你的環境任務總數: {total}')
print(f"  - TASK_DEF_KEY_ LIKE 'E%': {filtered_e} 筆")
print(f"  - TASK_DEF_KEY_ LIKE 'C%': {filtered_c} 筆")
print(f'  = 過濾後: {after_filter} 筆')

print()
print('【4. 筆數差異分析】')
print('-' * 60)

# 參考環境
ref_task = ref_client.query("SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'TASK'").result_rows[0][0]
ref_proc = ref_client.query("SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'PROC'").result_rows[0][0]
ref_total = ref_client.query("SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv").result_rows[0][0]

# 你的環境
my_view = my_client.query("SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE").result_rows[0][0]
my_rmv = my_client.query("SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE").result_rows[0][0]

print(f'參考環境 gold_proc_task_node_rmv:')
print(f'  - TASK: {ref_task} 筆')
print(f'  - PROC: {ref_proc} 筆')
print(f'  - 總計: {ref_total} 筆')
print()
print(f'你的環境:')
print(f'  - View: {my_view} 筆')
print(f'  - RMV: {my_rmv} 筆')
print()
print(f'差異原因:')
print(f'  1. 參考環境包含 PROC 記錄 ({ref_proc} 筆)，你的環境只有 TASK')
print(f'  2. 參考環境有過濾條件，你的環境沒有')
print(f'  3. 資料同步時間點可能不同')

print()
print('【5. 只比較 TASK 層的資料】')
print('-' * 60)

# 只比較 TASK
comparisons = [
    ("TASK 總筆數",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'TASK'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE"),
    ("TODO",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'TASK' AND node_state = 'TODO'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'TODO'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'TODO'"),
    ("DOING",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'TASK' AND node_state = 'DOING'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DOING'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DOING'"),
    ("DONE",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'TASK' AND node_state = 'DONE'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'"),
    ("DONE_AUTO",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'TASK' AND node_state = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'"),
    ("CANCELLED/TERMINATED",
     "SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'TASK' AND node_state = 'TERMINATED'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'"),
]

print(f"{'指標':<25} | {'Benchmark':>10} | {'View':>10} | {'RMV':>10}")
print("-" * 65)

for name, ref_sql, view_sql, rmv_sql in comparisons:
    ref_val = ref_client.query(ref_sql).result_rows[0][0]
    view_val = my_client.query(view_sql).result_rows[0][0]
    rmv_val = my_client.query(rmv_sql).result_rows[0][0]
    print(f"{name:<25} | {ref_val:>10} | {view_val:>10} | {rmv_val:>10}")

print()
print('=' * 80)
print('總結')
print('=' * 80)
print('1. TASK_STATUS 計算邏輯: ✅ 與參考環境一致')
print('2. 筆數差異原因:')
print('   - 參考環境包含 PROC (流程) 記錄')
print('   - 參考環境有過濾條件 (排除 E%/C% 開頭的 TASK_DEF_KEY_)')
print('   - 資料同步時間點不同')
print('3. 建議: 如需完全對齊，可加入相同的過濾條件')
