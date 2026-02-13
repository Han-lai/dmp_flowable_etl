import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
conn = pyodbc.connect(conn_str)

def check_11_24_categories():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-11-24'
    
    print(f"=== User-Task Audit for {target_date} ===")
    
    q = f"""
    WITH ConfigUsers AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    ),
    V3Members AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.EmpNodeRoleMapping_0202
        WHERE NodeCode LIKE '%%V3_%%'
    ),
    V3ConfigMembers AS (
        SELECT EmpCode FROM V3Members
        WHERE EmpCode IN (SELECT EmpCode FROM ConfigUsers)
    )
    SELECT 
        t.ASSIGNEE_ as EmpCode,
        t.NAME_,
        t.TASK_DEF_KEY_
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
    WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
      AND v.TEXT_ = '{line}'
      AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
      AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
    ORDER BY t.ASSIGNEE_
    """
    
    df = pd.read_sql(q, conn)
    
    summary = []
    for u in df['EmpCode'].unique():
        u_df = df[df['EmpCode'] == u]
        tasks = u_df['NAME_'].tolist()
        # Tags
        has_qc = any('QC' in t or 'IPQC' in t for t in tasks)
        has_qe = any('Quality Event' in t or '3.5.3.10' in t for t in tasks)
        has_st = any('Standard Time' in t or '3.5.3.11' in t for t in tasks)
        has_repair = any('Repair' in t or '3.5.3.5' in t for t in tasks)
        summary.append({'EmpCode': u, 'HasQC': has_qc, 'HasQE': has_qe, 'HasST': has_st, 'HasRepair': has_repair, 'Tasks': tasks})

    sdf = pd.DataFrame(summary)
    print(sdf.to_string(index=False))
    print(f"Total: {len(sdf)}")

if __name__ == "__main__":
    check_11_24_categories()
    conn.close()
