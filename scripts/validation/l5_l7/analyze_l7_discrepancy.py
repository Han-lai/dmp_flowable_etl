import pyodbc
import pandas as pd
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

# Connection Details
server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

def analyze_l7_key_dates():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    # Config Users (57)
    config_cte = f"""
    Candidates AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    ),
    ConfigUsers AS (
        SELECT DISTINCT EmpCode FROM Candidates
    )
    """
    
    # Key Dates: 25 (5), 28 (1), 30 (12)
    dates = ['2025-12-25', '2025-12-28', '2025-12-30']
    
    print(f"Connecting to MSSQL {server}...")
    try:
        conn = pyodbc.connect(conn_str)
        
        for target_date in dates:
            query = f"""
            WITH {config_cte},
            DailyTasks AS (
                SELECT 
                    t.ASSIGNEE_ as EmpCode,
                    t.TASK_DEF_KEY_,
                    t.NAME_
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                WHERE 
                    (
                        (t.END_TIME_ IS NOT NULL AND CAST(t.END_TIME_ AS DATE) = '{target_date}')
                        OR
                        (t.ASSIGNEE_ IS NOT NULL AND t.CLAIM_TIME_ IS NOT NULL 
                        AND CAST(t.CLAIM_TIME_ AS DATE) <= '{target_date}'
                        AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{target_date}'))
                    )
                    AND t.ASSIGNEE_ IN (SELECT EmpCode FROM ConfigUsers)
                    AND t.TASK_DEF_KEY_ LIKE '%V3_%'
            )
            SELECT 
                '{target_date}' as Date,
                TASK_DEF_KEY_,
                NAME_,
                COUNT(DISTINCT EmpCode) as UserCount
            FROM DailyTasks
            GROUP BY TASK_DEF_KEY_, NAME_
            ORDER BY UserCount DESC
            """
            
            df = pd.read_sql(query, conn)
            print(f"\n--- Date: {target_date} ---")
            print(df.to_string(index=False))
            print("-" * 50)
            
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_l7_key_dates()
