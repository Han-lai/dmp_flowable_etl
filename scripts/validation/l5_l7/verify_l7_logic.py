import pyodbc
import pandas as pd
import warnings
import sys

# Suppress warnings
warnings.filterwarnings("ignore")

# Connection Details
server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

def verify_l7_final_logic():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    # 1. Config User Logic (Confirmed):
    # Source: APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
    # Logic: Factory='NBU' AND LineName IN ('E5', '*')
    # Count: 35 (E5) + 22 (*) = 57 Users.
    config_cte = f"""
    Candidates AS (
        SELECT DISTINCT EmpCode, LineName
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    ),
    ConfigUsers AS (
        SELECT DISTINCT EmpCode FROM Candidates
    )
    """
    
    dates = pd.date_range(start='2025-12-25', end='2025-12-31').strftime('%Y-%m-%d').tolist()
    
    print(f"Connecting to MSSQL {server}...")
    try:
        conn = pyodbc.connect(conn_str)
        
        results = []
        for target_date in dates:
            query = f"""
            WITH {config_cte},
            ActiveUsers AS (
                SELECT DISTINCT t.ASSIGNEE_ as EmpCode
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                -- Active Logic:
                -- 1. Task Definition Key MUST contain 'V1_', 'V2_', or 'V3_'.
                -- 2. Task Status must be DONE or DOING (Implied by record existence in valid time window).
                -- 3. INTERSECT with ConfigUsers (Vx Member List).
                -- Note: Currently matches ~28 users. User expects ~5-12. 
                -- Implies additional filtering needed (e.g. exclude Repair keys).
                WHERE 
                    (
                        (t.END_TIME_ IS NOT NULL AND CAST(t.END_TIME_ AS DATE) = '{target_date}')
                        OR
                        (t.ASSIGNEE_ IS NOT NULL AND t.CLAIM_TIME_ IS NOT NULL 
                        AND CAST(t.CLAIM_TIME_ AS DATE) <= '{target_date}'
                        AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{target_date}'))
                    )
                    AND t.ASSIGNEE_ IN (SELECT EmpCode FROM ConfigUsers)
                    AND (
                        t.TASK_DEF_KEY_ LIKE '%V1_%' OR 
                        t.TASK_DEF_KEY_ LIKE '%V2_%' OR 
                        t.TASK_DEF_KEY_ LIKE '%V3_%'
                    )
            )
            SELECT 
                '{target_date}' as Date,
                (SELECT COUNT(*) FROM ConfigUsers) as Config,
                (SELECT COUNT(*) FROM ActiveUsers) as Active
            """
            
            df = pd.read_sql(query, conn)
            results.append(df)
            print(f"Date {target_date}: Config={df.iloc[0]['Config']}, Active={df.iloc[0]['Active']}")
            
        final_df = pd.concat(results)
        print("\n--- Final Results (Config=57, Active=V-Tasks) ---")
        print(final_df.to_string(index=False))
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_l7_final_logic()
