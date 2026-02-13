import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

def verify_l7_base_table():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    config_cte = f"""
    ConfigUsers AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    ),
    V3Members AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.EmpNodeRoleMapping_0202
        WHERE NodeCode LIKE '%V3_%'
    ),
    V3ConfigMembers AS (
        SELECT EmpCode FROM V3Members
        WHERE EmpCode IN (SELECT EmpCode FROM ConfigUsers)
    )
    """
    
    dates = pd.date_range(start='2025-12-25', end='2025-12-31').strftime('%Y-%m-%d').tolist()
    expected = [5, 9, 7, 1, 7, 12, 9]
    
    print(f"Connecting to MSSQL {server}...")
    try:
        conn = pyodbc.connect(conn_str)
        
        results = []
        for i, target_date in enumerate(dates):
            query = f"""
            WITH {config_cte},
            -- Base ACT_HI_TASKINST (no suffix)
            ActiveBase AS (
                SELECT DISTINCT t.ASSIGNEE_ as EmpCode
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST t
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST v 
                    ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
                WHERE t.END_TIME_ IS NOT NULL 
                    AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
                    AND t.TASK_DEF_KEY_ LIKE '%V3_%'
                    AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
                    AND v.TEXT_ = '{line}'
            ),
            -- _0108 suffix (our previous)
            Active0108 AS (
                SELECT DISTINCT t.ASSIGNEE_ as EmpCode
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v 
                    ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
                WHERE t.END_TIME_ IS NOT NULL 
                    AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
                    AND t.TASK_DEF_KEY_ LIKE '%V3_%'
                    AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
                    AND v.TEXT_ = '{line}'
            )
            SELECT 
                '{target_date}' as Date,
                (SELECT COUNT(*) FROM ActiveBase) as Base,
                (SELECT COUNT(*) FROM Active0108) as Snap0108,
                {expected[i]} as Expected
            """
            
            df = pd.read_sql(query, conn)
            results.append(df)
            b_ok = "OK" if df.iloc[0]['Base'] == expected[i] else f"+{df.iloc[0]['Base']-expected[i]}"
            s_ok = "OK" if df.iloc[0]['Snap0108'] == expected[i] else f"+{df.iloc[0]['Snap0108']-expected[i]}"
            print(f"{target_date}: Base={df.iloc[0]['Base']}[{b_ok}], 0108={df.iloc[0]['Snap0108']}[{s_ok}], Exp={expected[i]}")
            
        final_df = pd.concat(results)
        print("\n--- Results ---")
        print(final_df.to_string(index=False))
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_l7_base_table()
