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

def verify_refined_rule():
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
    
    results = []
    
    for i, target_date in enumerate(dates):
        query = f"""
        WITH {config_cte},
        ActiveUsers AS (
            SELECT DISTINCT 
                t.ASSIGNEE_ as EmpCode,
                t.TASK_DEF_KEY_,
                t.NAME_
            FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
            JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v 
                ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
            WHERE t.END_TIME_ IS NOT NULL 
                AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
                AND t.TASK_DEF_KEY_ LIKE '%V3_%'
                AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
                AND v.TEXT_ = '{line}'
        ),
        CoreUsers AS (
            SELECT DISTINCT EmpCode
            FROM ActiveUsers
            WHERE (TASK_DEF_KEY_ LIKE 'V3_5_2_%' OR TASK_DEF_KEY_ LIKE 'V3_5_3_%')
              AND NAME_ NOT LIKE '%Repair%'
              AND NAME_ NOT LIKE '%Validation%'
        )
        SELECT 
            '{target_date}' as Date,
            (SELECT COUNT(*) FROM CoreUsers) as RefinedActive,
            {expected[i]} as Expected
        """
        
        df = pd.read_sql(query, conn)
        results.append(df)
        match = "MATCH" if df.iloc[0]['RefinedActive'] == expected[i] else f"DIFF: {df.iloc[0]['RefinedActive'] - expected[i]}"
        print(f"Date {target_date}: RefinedActive={df.iloc[0]['RefinedActive']}, Expected={expected[i]} -> {match}")
        
    final_df = pd.concat(results)
    print("\n--- Final Comparison ---")
    print(final_df.to_string(index=False))
    print(f"\nTotal Absolute Error: {(final_df['RefinedActive'] - final_df['Expected']).abs().sum()}")

if __name__ == "__main__":
    verify_refined_rule()
    conn.close()
