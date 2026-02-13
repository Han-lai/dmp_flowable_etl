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

def check_11_27_assignment():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-11-27'
    
    print(f"=== Line Assignment for 9 Active Users on {target_date} ===")
    
    query = f"""
    WITH ConfigUsers AS (
        SELECT EmpCode, LineName as AssignedLine
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    )
    SELECT a.ASSIGNEE_ as EmpCode, c.AssignedLine
    FROM (
        SELECT DISTINCT t.ASSIGNEE_
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
          AND v.TEXT_ = 'E5'
          AND CAST(t.END_TIME_ AS DATE) = '2025-11-27'
    ) a
    JOIN ConfigUsers c ON a.ASSIGNEE_ = c.EmpCode
    ORDER BY a.ASSIGNEE_
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

if __name__ == "__main__":
    check_11_27_assignment()
    conn.close()
