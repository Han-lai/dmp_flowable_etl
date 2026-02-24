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

def detail_11_25():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-11-25'
    
    config_cte = f"""
    ConfigUsers AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('E5', '*')
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
    """
    
    print(f"=== User Activity on {target_date} ===")
    
    query = f"""
    WITH {config_cte}
    SELECT 
        t.ASSIGNEE_ as EmpCode,
        t.START_TIME_,
        t.END_TIME_,
        t.TASK_DEF_KEY_,
        CASE 
            WHEN CAST(t.END_TIME_ AS DATE) = '{target_date}' THEN 'DONE'
            WHEN (CAST(t.START_TIME_ AS DATE) <= '{target_date}' AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{target_date}')) THEN 'DOING'
            ELSE 'OTHER'
        END as Status
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
    WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
      AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
      AND v.TEXT_ = '{line}'
      AND (
        CAST(t.END_TIME_ AS DATE) = '{target_date}'
        OR (CAST(t.START_TIME_ AS DATE) <= '{target_date}' AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{target_date}'))
      )
    ORDER BY t.ASSIGNEE_, Status
    """
    
    df = pd.read_sql(query, conn)
    
    # Analyze by user
    user_summary = df.groupby('EmpCode').agg({
        'Status': lambda x: sorted(list(set(x))),
        'TASK_DEF_KEY_': lambda x: sorted(list(set(x)))
    }).reset_index()
    
    print(user_summary.to_string(index=False))
    print(f"Total Users: {len(user_summary)}")

if __name__ == "__main__":
    detail_11_25()
    conn.close()
