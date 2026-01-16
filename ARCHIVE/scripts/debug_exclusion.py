#!/usr/bin/env python3
"""Debug 排除條件的影響"""

import clickhouse_connect

local = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== Debug 排除條件的影響 ===')

# 1. 2025-12-28 建立的任務總數
print('\n1. 2025-12-28 建立的任務總數:')
result = local.query('''
    SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
''')
print(f'   總數: {result.result_rows[0][0]:,}')

# 2. 排除條件分布
print('\n2. 排除條件分布:')
result = local.query('''
    SELECT 
        is_excluded,
        exclude_reason,
        count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
    GROUP BY is_excluded, exclude_reason
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   is_excluded={row[0]}, reason={row[1]}: {row[2]:,}')

# 3. 不排除的任務數
print('\n3. 不排除的任務數 (is_excluded = 0):')
result = local.query('''
    SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND is_excluded = 0
''')
print(f'   數量: {result.result_rows[0][0]:,}')

# 4. 檢查外部系統的排除邏輯
print('\n4. 外部系統的排除邏輯:')
print('   silver_enriched_taskinst WHERE 條件:')
print('   - TASK_DEF_KEY_ NOT LIKE E%')
print('   - TASK_DEF_KEY_ NOT LIKE C%')
print('   - proc_mo_number NOT LIKE Q%')
print('   - proc_mo_number NOT LIKE R%')
print('   - 沒有排除 Bypass 任務！')

# 5. 如果不排除 Bypass，本地系統的數量
print('\n5. 如果不排除 Bypass，本地系統的數量:')
result = local.query('''
    SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND (exclude_reason IS NULL OR exclude_reason NOT IN ('E_prefix', 'C_prefix', 'Q_order', 'R_order'))
''')
print(f'   數量: {result.result_rows[0][0]:,}')

# 6. 只排除 E/C/Q/R，不排除 Bypass
print('\n6. 只排除 E/C/Q/R，不排除 Bypass:')
result = local.query('''
    SELECT 
        multiIf(
            task_end_time IS NOT NULL AND toDate(task_end_time) <= toDate('2025-12-28'), 'DONE',
            task_claim_time IS NOT NULL AND toDate(task_claim_time) <= toDate('2025-12-28'), 'DOING',
            'TODO'
        ) AS state_on_date,
        count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND task_definition_key NOT LIKE 'E%'
      AND task_definition_key NOT LIKE 'C%'
      AND (proc_name IS NULL OR (proc_name NOT LIKE 'Q%' AND proc_name NOT LIKE 'R%'))
    GROUP BY state_on_date
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')
