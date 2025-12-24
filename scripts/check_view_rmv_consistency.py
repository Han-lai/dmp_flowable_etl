import clickhouse_connect

client = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== View vs RMV 資料一致性比較 ===\n')

# 1. 筆數比較
print('--- 1. 筆數比較 ---')
tables = [
    ('V_PROC_VARIABLES_PIVOTED', 'RMV_PROC_VARIABLES_PIVOTED'),
    ('V_HI_PROC_TASK_NODE', 'RMV_HI_PROC_TASK_NODE'),
    ('V_HI_PROCINST_NODE', 'RMV_HI_PROCINST_NODE'),
    ('V_HI_BIZ_EVENT_INFO', 'RMV_HI_BIZ_EVENT_INFO'),
]

all_match = True
for view, rmv in tables:
    v_cnt = client.query(f'SELECT count(*) FROM silver.{view}').result_rows[0][0]
    r_cnt = client.query(f'SELECT count(*) FROM silver.{rmv} FINAL').result_rows[0][0]
    match = 'OK' if v_cnt == r_cnt else 'DIFF'
    if v_cnt != r_cnt:
        all_match = False
    print(f'{view:<30} View: {v_cnt:>8} | RMV: {r_cnt:>8} | {match}')

# 2. TASK_STATUS 分布比較
print('\n--- 2. TASK_STATUS 分布比較 ---')
v_result = client.query('SELECT TASK_STATUS, count(*) FROM silver.V_HI_PROC_TASK_NODE GROUP BY TASK_STATUS ORDER BY TASK_STATUS')
r_result = client.query('SELECT TASK_STATUS, count(*) FROM silver.RMV_HI_PROC_TASK_NODE FINAL GROUP BY TASK_STATUS ORDER BY TASK_STATUS')

v_dict = {row[0]: row[1] for row in v_result.result_rows}
r_dict = {row[0]: row[1] for row in r_result.result_rows}

print(f"{'STATUS':<15} | {'View':>10} | {'RMV':>10} | Match")
print('-' * 50)
for status in sorted(set(v_dict.keys()) | set(r_dict.keys())):
    v = v_dict.get(status, 0)
    r = r_dict.get(status, 0)
    match = 'OK' if v == r else 'DIFF'
    if v != r:
        all_match = False
    print(f'{status:<15} | {v:>10} | {r:>10} | {match}')

# 3. PROC_STATE 分布比較
print('\n--- 3. PROC_STATE 分布比較 ---')
v_result = client.query('SELECT PROC_STATE, count(*) FROM silver.V_HI_PROCINST_NODE GROUP BY PROC_STATE ORDER BY PROC_STATE')
r_result = client.query('SELECT PROC_STATE, count(*) FROM silver.RMV_HI_PROCINST_NODE FINAL GROUP BY PROC_STATE ORDER BY PROC_STATE')

v_dict = {row[0]: row[1] for row in v_result.result_rows}
r_dict = {row[0]: row[1] for row in r_result.result_rows}

print(f"{'STATE':<15} | {'View':>10} | {'RMV':>10} | Match")
print('-' * 50)
for state in sorted(set(v_dict.keys()) | set(r_dict.keys())):
    v = v_dict.get(state, 0)
    r = r_dict.get(state, 0)
    match = 'OK' if v == r else 'DIFF'
    if v != r:
        all_match = False
    print(f'{state:<15} | {v:>10} | {r:>10} | {match}')

# 4. BIZ_EVENT 指標比較
print('\n--- 4. BIZ_EVENT 聚合指標比較 ---')
metrics = [
    ('PROCESS_COUNT 總和', 'sum(PROCESS_COUNT)'),
    ('TASK_TODO_CNT 總和', 'sum(TASK_TODO_CNT)'),
    ('TASK_DOING_CNT 總和', 'sum(TASK_DOING_CNT)'),
    ('TASK_DONE_CNT 總和', 'sum(TASK_DONE_CNT)'),
    ('IS_IN_PROGRESS 總和', 'sum(IS_IN_PROGRESS)'),
]

for name, agg in metrics:
    v = client.query(f'SELECT {agg} FROM silver.V_HI_BIZ_EVENT_INFO').result_rows[0][0]
    r = client.query(f'SELECT {agg} FROM silver.RMV_HI_BIZ_EVENT_INFO FINAL').result_rows[0][0]
    match = 'OK' if v == r else 'DIFF'
    if v != r:
        all_match = False
    print(f'{name:<25} View: {v:>10} | RMV: {r:>10} | {match}')

# 總結
print('\n' + '=' * 50)
if all_match:
    print('結論: View 與 RMV 資料完全一致')
else:
    print('結論: View 與 RMV 資料存在差異')
