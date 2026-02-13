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

def analyze_11_27():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-11-27'
    
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
    
    print(f"=== Active Users (Done) on {target_date} ===")
    query = f"""
    WITH {config_cte}
    SELECT DISTINCT 
        t.ASSIGNEE_ as EmpCode,
        h.EmpName,
        h.DeptCodeLname,
        h.JobFamilyName,
        h.JobCode
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
    LEFT JOIN APP_SRV_COMMON.dbo.HR_Employee_0202 h ON t.ASSIGNEE_ = h.EmpCode
    WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
      AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
      AND v.TEXT_ = '{line}'
      AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
    ORDER BY t.ASSIGNEE_
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))
    print(f"Total: {len(df)}")

if __name__ == "__main__":
    analyze_11_27()
    conn.close()
