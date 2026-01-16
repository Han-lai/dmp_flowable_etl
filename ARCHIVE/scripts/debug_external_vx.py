#!/usr/bin/env python3
"""Debug 外部系統的 Vx 問題"""

import clickhouse_connect

ext = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print('=== Debug 外部系統的 Vx 問題 ===')

# 關鍵問題：silver_enriched_procinst 有 proc_vx，但 silver_enriched_taskinst 的 proc_vx 全是 NULL

# 1. 檢查 silver_enriched_taskinst 的 proc_vx 欄位來源
print('\n1. silver_enriched_taskinst 的 proc_vx 欄位來源:')
print('   從 CREATE TABLE 語句可以看到:')
print('   p.proc_vx AS proc_vx')
print('   其中 p 是 LEFT JOIN silver_enriched_procinst')

# 2. 檢查 JOIN 是否成功
print('\n2. 檢查 JOIN 是否成功:')
result = ext.query('''
    SELECT 
        count() AS total,
        countIf(proc_inst_id IS NOT NULL) AS has_proc_inst_id,
        countIf(proc_inst_id IS NULL) AS no_proc_inst_id
    FROM silver_enriched_taskinst
''')
row = result.result_rows[0]
print(f'   總數: {row[0]:,}, 有 proc_inst_id: {row[1]:,}, 無 proc_inst_id: {row[2]:,}')

# 3. 直接查詢 JOIN 結果
print('\n3. 直接查詢 JOIN 結果:')
result = ext.query('''
    SELECT 
        t.task_id,
        t.proc_inst_id,
        t.proc_vx AS task_proc_vx,
        p.proc_vx AS procinst_proc_vx
    FROM silver_enriched_taskinst t
    LEFT JOIN silver_enriched_procinst p ON t.proc_inst_id = p.proc_inst_id
    LIMIT 5
''')
for row in result.result_rows:
    print(f'   task_id={row[0][:20]}..., proc_inst_id={row[1][:20] if row[1] else None}..., task_proc_vx={row[2]}, procinst_proc_vx={row[3]}')

# 4. 檢查 silver_enriched_taskinst 是物化視圖，proc_vx 是在建立時計算的
print('\n4. 問題分析:')
print('   silver_enriched_taskinst 是物化視圖 (REFRESH EVERY 1 DAY)')
print('   proc_vx 是在物化視圖建立時從 silver_enriched_procinst JOIN 過來的')
print('   但是 silver_enriched_procinst 也是物化視圖')
print('   如果 silver_enriched_procinst 在 silver_enriched_taskinst 之後刷新，')
print('   那麼 silver_enriched_taskinst 的 proc_vx 就會是 NULL')

# 5. 檢查物化視圖的刷新時間
print('\n5. 檢查物化視圖的刷新狀態:')
result = ext.query('''
    SELECT 
        database,
        view,
        status,
        last_refresh_time,
        next_refresh_time
    FROM system.view_refreshes
    WHERE database = 'flowable_analytics'
''')
for row in result.result_rows:
    print(f'   {row[1]}: status={row[2]}, last_refresh={row[3]}, next_refresh={row[4]}')

# 6. 檢查 gold_daily_task_metrics 的 proc_vx 分布
print('\n6. gold_daily_task_metrics 的 proc_vx 分布:')
result = ext.query('''
    SELECT proc_vx, count() AS cnt
    FROM gold_daily_task_metrics
    GROUP BY proc_vx
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')
