#!/usr/bin/env python3
"""檢查符合條件的任務是否有 region"""
import pymssql

conn = pymssql.connect(
    server='twtpesqldv2.delta.corp',
    port='1433',
    user='DMP_APP_SRV',
    password='APP@DB#01',
    database='APP_SRV_BPM'
)
cursor = conn.cursor()

# 取得符合條件的 ProcessInstanceId
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT t.ProcessInstanceId, t.TaskId, t.TaskStatus, t.Plant, t.Factory, t.Line
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND t.TaskBypass = 'N'
      AND t.TaskDefinitionKey NOT LIKE 'E%'
      AND t.TaskDefinitionKey NOT LIKE 'C%'
      AND (t.TaskDefinitionKey LIKE 'V1%'
          OR v.moNumber LIKE '196%' OR v.moNumber LIKE '199%' OR v.moNumber LIKE '200%'
          OR v.moNumber LIKE '210%' OR v.moNumber LIKE '212%' OR v.moNumber LIKE '213%'
          OR v.moNumber LIKE '315%')
      AND t.Plant = 'WJ2'
      AND t.Factory = 'NBU'
      AND t.Line = 'E5'
""")
rows = cursor.fetchall()
print(f"符合條件的任務: {len(rows)} 筆")
print()

proc_ids = list(set([row[0] for row in rows]))
print(f"不重複的 ProcessInstanceId: {len(proc_ids)} 個")
print()

print("檢查這些 ProcessInstanceId 在 varinst 中是否有 region:")
for proc_id in proc_ids:
    cursor.execute(f"""
        SELECT NAME_, TEXT_ 
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST 
        WHERE PROC_INST_ID_ = '{proc_id}' AND NAME_ = 'region'
    """)
    region_rows = cursor.fetchall()
    if region_rows:
        print(f"  {proc_id}: {region_rows}")
    else:
        print(f"  {proc_id}: 無 region")

conn.close()
