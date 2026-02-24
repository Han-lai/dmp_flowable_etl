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

def analyze_nov_tasks():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-11-24'
    
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
    
    print(f"=== Tasks on {target_date} for Configured V3 Users ===")
    df = pd.read_sql(f"""
    WITH {config_cte}
    SELECT DISTINCT 
        t.ASSIGNEE_ as EmpCode,
        t.TASK_DEF_KEY_,
        t.NAME_
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v 
        ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
    WHERE t.END_TIME_ IS NOT NULL 
        AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
        AND t.TASK_DEF_KEY_ LIKE '%%V3_%%'
        AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
        AND v.TEXT_ = '{line}'
    ORDER BY t.ASSIGNEE_
    """, conn)
    
    users = df['EmpCode'].unique()
    print(f"Total Active Users in ACT_HI: {len(users)}")
    for u in users:
        u_tasks = df[df['EmpCode'] == u]
        task_names = u_tasks['NAME_'].tolist()
        task_keys = u_tasks['TASK_DEF_KEY_'].tolist()
        # Highlight non-3.5.2/3 tasks
        non_core = any(not (k.startswith('V3_5_2') or k.startswith('V3_5_3')) for k in task_keys)
        print(f"  {u} {'[*]' if non_core else '   '}: {task_keys}")

if __name__ == "__main__":
    analyze_nov_tasks()
    conn.close()
