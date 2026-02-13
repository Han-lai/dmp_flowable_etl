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

def check_11_25_lines():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-11-25'
    
    print(f"=== Line Assignment for Active Users (Done or Doing) on {target_date} ===")
    
    query = f"""
    WITH ConfigUsers AS (
        SELECT EmpCode, LineName as AssignedLine
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
        SELECT c.EmpCode, c.AssignedLine 
        FROM ConfigUsers c
        JOIN V3Members v ON c.EmpCode = v.EmpCode
    ),
    ActiveTasks AS (
        SELECT DISTINCT 
            t.ASSIGNEE_ as EmpCode,
            CASE 
                WHEN CAST(t.END_TIME_ AS DATE) = '{target_date}' THEN 'DONE'
                ELSE 'DOING'
            END as Status
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
          AND v.TEXT_ = '{line}'
          AND (
            CAST(t.END_TIME_ AS DATE) = '{target_date}'
            OR (CAST(t.START_TIME_ AS DATE) <= '{target_date}' AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{target_date}'))
          )
    )
    SELECT a.EmpCode, m.AssignedLine, a.Status
    FROM ActiveTasks a
    LEFT JOIN V3ConfigMembers m ON a.EmpCode = m.EmpCode
    ORDER BY a.EmpCode, a.Status
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))
    
    print("\nSummary by Line assignment:")
    print(df.groupby(['AssignedLine', 'Status'])['EmpCode'].nunique())

if __name__ == "__main__":
    check_11_25_lines()
    conn.close()
