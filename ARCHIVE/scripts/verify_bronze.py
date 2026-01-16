#!/usr/bin/env python3
"""驗證 Bronze 層資料"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

tables = [
    'bronze.bpm_act_hi_procinst',
    'bronze.bpm_act_hi_taskinst',
    'bronze.bpm_act_hi_identitylink',
    'bronze.bpm_act_hi_varinst',
    'bronze.bpm_act_re_procdef',
    'bronze.common_flowable_task_stats',
    'bronze.common_hr_employee',
    'bronze.common_process_role_user_mapping',
]

print('=== Bronze 層資料驗證 ===')
print(f'{"表名":<45} {"筆數":<15}')
print('-' * 60)

for table in tables:
    try:
        result = c.query(f'SELECT count() FROM {table}')
        cnt = result.result_rows[0][0]
        print(f'{table:<45} {cnt:>12,}')
    except Exception as e:
        print(f'{table:<45} ERROR: {e}')
