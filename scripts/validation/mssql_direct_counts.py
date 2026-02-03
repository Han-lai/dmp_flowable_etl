
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

# 1. User's exact logic on FlowableTaskStats_0202 (No Plant/Line filter)
query_total = """
SELECT count(*) FROM FlowableTaskStats_0202 i
WHERE (
    CAST(i.TaskCreateDate AS DATE) = '2025-12-25'
    OR CAST(i.TaskEndDate AS DATE) = '2025-12-25'
    OR CAST(i.TaskClaimDate AS DATE) = '2025-12-25'
)
and i.TaskBypass ='N' and i.TaskStatus  in ('DONE')
and i.MoNumber not in ('E','C','Q','R')
"""

# 2. Same logic but filtered for WJ2/NBU/E5 (as per previous context)
query_e5 = """
SELECT count(*) FROM FlowableTaskStats_0202 i
WHERE (
    CAST(i.TaskCreateDate AS DATE) = '2025-12-25'
    OR CAST(i.TaskEndDate AS DATE) = '2025-12-25'
    OR CAST(i.TaskClaimDate AS DATE) = '2025-12-25'
)
and i.TaskBypass ='N' and i.TaskStatus  in ('DONE')
and i.MoNumber not in ('E','C','Q','R')
AND i.Plant = 'WJ2' AND i.LineName = 'E5'
"""

# 3. Check for 'flowable_analytics' if it's a schema in APP_SRV_COMMON
query_schema = "SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'flowable_analytics'"

print("--- MSSQL Direct Connection Verification ---")
count_total = run_query(query_total)
print(f"Total Count (Exact Logic, No Plant/Line Filter): {count_total}")

count_e5 = run_query(query_e5)
print(f"E5 Filtered Count (WJ2/E5): {count_e5}")

schema_exists = run_query(query_schema)
print(f"Schema 'flowable_analytics' exists: {'Yes' if schema_exists == 1 else 'No'}")

# Double check table FlowableTaskStats (not _0202)
query_std = query_total.replace("FlowableTaskStats_0202", "FlowableTaskStats")
count_std = run_query(query_std)
print(f"Total Count (using 'FlowableTaskStats' table): {count_std}")
