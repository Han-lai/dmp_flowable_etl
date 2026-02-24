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

def check_11_24_job_levels():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-11-24'
    
    print(f"=== Job Codes for 14 Active Users on {target_date} ===")
    
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
    
    query = f"""
    WITH {config_cte},
    ActiveUsers AS (
        SELECT DISTINCT t.ASSIGNEE_ as EmpCode
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
          AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
          AND v.TEXT_ = '{line}'
          AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
    )
    SELECT a.EmpCode, h.EmpName, h.JobFamilyName, h.JobCode
    FROM ActiveUsers a
    LEFT JOIN APP_SRV_COMMON.dbo.HR_Employee_0202 h ON a.EmpCode = h.EmpCode
    ORDER BY h.JobCode DESC
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

if __name__ == "__main__":
    check_11_24_job_levels()
    conn.close()
