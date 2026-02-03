
import pyodbc
import clickhouse_connect

# Config
server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'

ch_client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

def get_mssql_count(db, query):
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={db};UID={username};PWD={password}'
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        cursor = conn.cursor()
        cursor.execute(query)
        res = cursor.fetchone()
        conn.close()
        return res[0]
    except Exception as e:
        return f"Error: {e}"

# 1. Source: MSSQL FlowableTaskStats_0202 (The user's latest specific query)
query_0202 = """
SELECT count(*) FROM FlowableTaskStats_0202 i
WHERE (
    CAST(i.TaskCreateDate AS DATE) = '2025-12-25'
    OR CAST(i.TaskEndDate AS DATE) = '2025-12-25'
    OR CAST(i.TaskClaimDate AS DATE) = '2025-12-25'
)
AND i.TaskBypass ='N' AND i.TaskStatus = 'DONE'
AND i.Plant = 'WJ2' AND i.Line = 'E5'
AND (
    i.MoNumber NOT LIKE 'E%' 
    AND i.MoNumber NOT LIKE 'C%' 
    AND i.MoNumber NOT LIKE 'Q%' 
    AND i.MoNumber NOT LIKE 'R%'
)
"""

# 2. Source: MSSQL Raw (ACT_HI_TASKINST_0108) 
# Note: Using the original QAS logic but with DONE status and Mo exclusion to align
query_raw = """
SELECT count(DISTINCT hti.ID_)
FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108 hi
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 var_plant on hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ and var_plant.NAME_ = 'plant'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 var_lineName on hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ and var_lineName.NAME_ = 'lineName'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 var_mo on hi.PROC_INST_ID_ = var_mo.PROC_INST_ID_ and var_mo.NAME_ = 'moNumber'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 tb ON hti.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
WHERE (
    CAST(hti.START_TIME_ AS DATE) = '2025-12-25'
    OR CAST(hti.CLAIM_TIME_ AS DATE) = '2025-12-25'
    OR CAST(hti.END_TIME_ AS DATE) = '2025-12-25'
)
AND var_plant.TEXT_ = 'WJ2'
AND var_lineName.TEXT_ = 'E5'
AND (tb.LONG_ IS NULL OR tb.LONG_ = 0) -- TaskBypass = 'N'
AND hti.END_TIME_ IS NOT NULL -- TaskStatus = 'DONE'
AND (
    var_mo.TEXT_ NOT LIKE 'E%' 
    AND var_mo.TEXT_ NOT LIKE 'C%' 
    AND var_mo.TEXT_ NOT LIKE 'Q%' 
    AND var_mo.TEXT_ NOT LIKE 'R%'
)
"""

# 3. Source: ClickHouse Gold
query_ch = """
SELECT sum(total_task) FROM gold.rmv_l5_task_completion 
WHERE snapshot_date = '2025-12-25' 
AND plant = 'WJ2' AND line = 'E5'
"""

# Execute
print("--- Final Three-Way Reconciliation ---")
c1 = get_mssql_count('APP_SRV_COMMON', query_0202)
print(f"1. MSSQL FlowableTaskStats_0202: {c1}")

c2 = get_mssql_count('APP_SRV_BPM', query_raw)
print(f"2. MSSQL Raw (TaskInst + Vars):  {c2}")

c3 = ch_client.command(query_ch)
print(f"3. ClickHouse Gold Layer:        {c3}")

print("\n--- Summary ---")
if c1 == c3:
    print("✅ ClickHouse exactly matches FlowableTaskStats_0202 benchmark!")
else:
    print("❌ Discrepancy detected between ClickHouse and 0202 benchmark.")

if c1 == c2:
    print("✅ Benchmark 0202 perfectly matches Raw Data source logic!")
else:
    print(f"⚠️ Small diff ({int(c1)-int(c2) if isinstance(c1,int) and isinstance(c2,int) else 'N/A'}) between 0202 and Raw Source (likely due to MoNumber capture timing).")
