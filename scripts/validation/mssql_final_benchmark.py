
import pyodbc

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_COMMON'

def run_query(query):
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        cursor = conn.cursor()
        cursor.execute(query)
        res = cursor.fetchone()
        conn.close()
        return res[0]
    except Exception as e:
        return str(e)

# Columns likely: Plant, Factory, Line, ProductionArea...
query_e5 = """
SELECT count(*) FROM FlowableTaskStats_0202 i
WHERE (
    CAST(i.TaskCreateDate AS DATE) = '2025-12-25'
    OR CAST(i.TaskEndDate AS DATE) = '2025-12-25'
    OR CAST(i.TaskClaimDate AS DATE) = '2025-12-25'
)
and i.TaskBypass ='N' and i.TaskStatus  in ('DONE')
and (
    i.MoNumber NOT LIKE 'E%' 
    AND i.MoNumber NOT LIKE 'C%' 
    AND i.MoNumber NOT LIKE 'Q%' 
    AND i.MoNumber NOT LIKE 'R%'
)
AND i.Plant = 'WJ2' AND i.Line = 'E5'
"""

print("--- MSSQL Direct Connection Final Count ---")
count_e5 = run_query(query_e5)
print(f"FlowableTaskStats_0202 (WJ2/E5, 2025-12-25): {count_e5}")
