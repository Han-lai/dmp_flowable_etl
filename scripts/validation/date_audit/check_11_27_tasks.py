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

def check_11_27_tasks():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-11-27'
    
    print(f"=== Tasks for 9 Active Users on {target_date} ===")
    
    query = f"""
    SELECT 
        t.ASSIGNEE_ as EmpCode,
        t.TASK_DEF_KEY_,
        t.NAME_
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
    WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
      AND v.TEXT_ = 'E5'
      AND CAST(t.END_TIME_ AS DATE) = '2025-11-27'
    ORDER BY t.ASSIGNEE_
    """
    
    df = pd.read_sql(query, conn)
    
    for u in df['EmpCode'].unique():
        u_df = df[df['EmpCode'] == u]
        print(f"User {u}:")
        for _, r in u_df.iterrows():
            print(f"  - {r['TASK_DEF_KEY_']} {r['NAME_']}")

if __name__ == "__main__":
    check_11_27_tasks()
    conn.close()
