#!/usr/bin/env python3
"""比較原始表和 _0106 表的資料量"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

tables = [
    ('ACT_HI_PROCINST', 'ACT_HI_PROCINST_0106'),
    ('ACT_HI_TASKINST', 'ACT_HI_TASKINST_0106'),
    ('ACT_HI_IDENTITYLINK', 'ACT_HI_IDENTITYLINK_0106'),
    ('ACT_HI_VARINST', 'ACT_HI_VARINST_0106'),
    ('ACT_RE_PROCDEF', 'ACT_RE_PROCDEF_0106'),
]

print('=== 比較原始表和 _0106 表的資料量 ===')
print(f'{"表名":<30} {"原始表":<15} {"_0106 表":<15}')
print('-' * 60)

for orig, new in tables:
    try:
        # 原始表
        sql1 = f"SELECT count() FROM jdbc('mssql_master', 'SELECT 1 FROM APP_SRV_BPM.dbo.{orig}')"
        cnt1 = c.query(sql1).result_rows[0][0]
    except:
        cnt1 = 'N/A'
    
    try:
        # _0106 表
        sql2 = f"SELECT count() FROM jdbc('mssql_master', 'SELECT 1 FROM APP_SRV_BPM.dbo.{new}')"
        cnt2 = c.query(sql2).result_rows[0][0]
    except:
        cnt2 = 'N/A'
    
    print(f'{orig:<30} {str(cnt1):<15} {str(cnt2):<15}')
