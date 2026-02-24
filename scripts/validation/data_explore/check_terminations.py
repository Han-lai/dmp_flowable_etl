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

def check_terminations():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    print("=== Checking Terminations for Config Users ===")
    
    query = f"""
    SELECT h.EmpCode, h.EmpName, h.TerminateDate, h.JobFamilyName
    FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202 p
    JOIN APP_SRV_COMMON.dbo.HR_Employee_0202 h ON p.EmpCode = h.EmpCode
    WHERE p.Plant = '{plant}' AND p.Factory = '{factory}' 
      AND p.LineName IN ('{line}', '*')
      AND h.TerminateDate IS NOT NULL
    ORDER BY h.TerminateDate
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

if __name__ == "__main__":
    check_terminations()
    conn.close()
