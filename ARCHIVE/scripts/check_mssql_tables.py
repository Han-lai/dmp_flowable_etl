#!/usr/bin/env python3
"""檢查 MSSQL 表是否存在"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== 檢查 MSSQL 原始表 ===')
tables = [
    'ACT_HI_PROCINST', 
    'ACT_HI_TASKINST', 
    'ACT_HI_IDENTITYLINK', 
    'ACT_HI_VARINST', 
    'ACT_RE_PROCDEF',
    'ACT_HI_PROCINST_0106', 
    'ACT_HI_TASKINST_0106', 
    'ACT_HI_IDENTITYLINK_0106', 
    'ACT_HI_VARINST_0106', 
    'ACT_RE_PROCDEF_0106',
]

for t in tables:
    try:
        sql = f"SELECT count() FROM jdbc('mssql_master', 'APP_SRV_BPM.dbo', '{t}')"
        rows = c.query(sql).result_rows
        print(f'{t}: {rows[0][0]:,} 筆')
    except Exception as e:
        err_msg = str(e)
        if 'Invalid object name' in err_msg:
            print(f'{t}: 表不存在')
        else:
            print(f'{t}: 錯誤 - {err_msg[:100]}')
