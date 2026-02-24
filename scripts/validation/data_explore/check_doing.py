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

def check_doing_tasks():
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
    
    print(f"=== Active Users on {target_date} (Including Doing) ===")
    
    # Logic for "Active" on a day often includes anyone who had a task in progress:
    # 1. EndTime is on target_date (Done)
    # 2. StartTime <= target_date AND (EndTime > target_date OR EndTime IS NULL) (Doing)
    
    query = f"""
    WITH {config_cte},
    ActiveUsers AS (
        SELECT DISTINCT t.ASSIGNEE_ as EmpCode
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
          AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
          AND v.TEXT_ = '{line}'
          AND (
            CAST(t.END_TIME_ AS DATE) = '{target_date}'
            OR (CAST(t.START_TIME_ AS DATE) <= '{target_date}' AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{target_date}'))
          )
    )
    SELECT COUNT(*) as Count FROM ActiveUsers
    """
    
    df = pd.read_sql(query, conn)
    print(f"Total Active Users (Done + Doing): {df.iloc[0]['Count']}")
    
    # List the users
    query_list = f"""
    WITH {config_cte}
    SELECT DISTINCT t.ASSIGNEE_ as EmpCode, t.START_TIME_, t.END_TIME_, t.NAME_
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
    WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
      AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
      AND v.TEXT_ = '{line}'
      AND (
        CAST(t.END_TIME_ AS DATE) = '{target_date}'
        OR (CAST(t.START_TIME_ AS DATE) <= '{target_date}' AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{target_date}'))
      )
    ORDER BY t.ASSIGNEE_
    """
    df_list = pd.read_sql(query_list, conn)
    print(df_list.to_string(index=False))

if __name__ == "__main__":
    check_doing_tasks()
    conn.close()
