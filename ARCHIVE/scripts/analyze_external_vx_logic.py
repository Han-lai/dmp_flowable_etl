#!/usr/bin/env python3
"""分析外部系統的 Vx 歸屬邏輯"""

import clickhouse_connect

ext = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print('=== 分析外部系統的 Vx 歸屬邏輯 ===')

# 外部系統的 proc_vx 計算邏輯（從 silver_enriched_procinst）:
print('''
外部系統的 proc_vx 計算邏輯:
================================================================================
multiIf(
    -- 條件 1: MoNumber 以特定數字開頭 → V1_NPE 或 V1_MFG
    (pv.proc_mo_number LIKE '196%') OR 
    (pv.proc_mo_number LIKE '199%') OR 
    (pv.proc_mo_number LIKE '200%') OR 
    (pv.proc_mo_number LIKE '210%') OR 
    (pv.proc_mo_number LIKE '212%') OR   -- 注意：212% 重複了
    (pv.proc_mo_number LIKE '212%') OR   -- 重複！
    (pv.proc_mo_number LIKE '213%') OR 
    (pv.proc_mo_number LIKE '315%'), 
        multiIf(pv.proc_factory LIKE '%NPE%', 'V1_NPE', 'V1_MFG'),
    
    -- 條件 2: PROC_DEF_KEY 以 V1_ 開頭 → V1_NPE 或 V1_MFG
    pd.KEY_ LIKE 'V1_%', 
        multiIf(pv.proc_factory LIKE '%NPE%', 'V1_NPE', 'V1_MFG'),
    
    -- 條件 3: PROC_DEF_KEY 以 V2_ 開頭 → V2
    pd.KEY_ LIKE 'V2_%', 'V2',
    
    -- 條件 4: PROC_DEF_KEY 以 V3_ 開頭 → V3
    pd.KEY_ LIKE 'V3_%', 'V3',
    
    -- 其他 → NULL
    NULL
) AS proc_vx
================================================================================
''')

# 1. 檢查 silver_enriched_procinst 的 proc_vx 分布
print('1. silver_enriched_procinst 的 proc_vx 分布:')
result = ext.query('''
    SELECT proc_vx, count() AS cnt
    FROM silver_enriched_procinst
    GROUP BY proc_vx
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 2. 檢查 proc_vx 為 NULL 的原因
print('\n2. proc_vx 為 NULL 的原因分析:')
result = ext.query('''
    SELECT 
        substring(proc_def_key, 1, 3) AS key_prefix,
        count() AS cnt
    FROM silver_enriched_procinst
    WHERE proc_vx IS NULL
    GROUP BY key_prefix
    ORDER BY cnt DESC
    LIMIT 10
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 3. 檢查 silver_enriched_taskinst 的 proc_vx 分布
print('\n3. silver_enriched_taskinst 的 proc_vx 分布:')
result = ext.query('''
    SELECT proc_vx, count() AS cnt
    FROM silver_enriched_taskinst
    GROUP BY proc_vx
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 4. 檢查 silver_enriched_taskinst 的 task_def_key 前綴分布
print('\n4. silver_enriched_taskinst 的 task_def_key 前綴分布:')
result = ext.query('''
    SELECT 
        substring(task_def_key, 1, 2) AS prefix,
        count() AS cnt
    FROM silver_enriched_taskinst
    GROUP BY prefix
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 5. 檢查為什麼 proc_vx 全部是 NULL
print('\n5. 檢查 silver_enriched_taskinst 的 proc_inst_id 是否有對應的 procinst:')
result = ext.query('''
    SELECT 
        count() AS total,
        countIf(p.proc_vx IS NOT NULL) AS has_vx,
        countIf(p.proc_vx IS NULL) AS no_vx
    FROM silver_enriched_taskinst t
    LEFT JOIN silver_enriched_procinst p ON t.proc_inst_id = p.proc_inst_id
''')
row = result.result_rows[0]
print(f'   總數: {row[0]:,}, 有 Vx: {row[1]:,}, 無 Vx: {row[2]:,}')

# 6. 檢查 silver_enriched_procinst 的 proc_def_key 前綴分布
print('\n6. silver_enriched_procinst 的 proc_def_key 前綴分布:')
result = ext.query('''
    SELECT 
        substring(proc_def_key, 1, 3) AS prefix,
        count() AS cnt
    FROM silver_enriched_procinst
    GROUP BY prefix
    ORDER BY cnt DESC
    LIMIT 10
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 7. 檢查 proc_def_key 以 V1_/V2_/V3_ 開頭的數量
print('\n7. proc_def_key 以 V1_/V2_/V3_ 開頭的數量:')
result = ext.query('''
    SELECT 
        countIf(proc_def_key LIKE 'V1_%') AS v1_count,
        countIf(proc_def_key LIKE 'V2_%') AS v2_count,
        countIf(proc_def_key LIKE 'V3_%') AS v3_count,
        countIf(proc_def_key NOT LIKE 'V1_%' AND proc_def_key NOT LIKE 'V2_%' AND proc_def_key NOT LIKE 'V3_%') AS other_count
    FROM silver_enriched_procinst
''')
row = result.result_rows[0]
print(f'   V1_: {row[0]:,}, V2_: {row[1]:,}, V3_: {row[2]:,}, 其他: {row[3]:,}')
