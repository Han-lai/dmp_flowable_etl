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

def verify_no_qc_rule():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
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
                t.NAME_
            FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
            JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v 
                ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
            WHERE t.END_TIME_ IS NOT NULL 
                AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
                AND t.TASK_DEF_KEY_ LIKE 'V3_5_[23]_%%'
                AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
                AND v.TEXT_ = '{line}'
        ),
        FilterUsers AS (
            SELECT DISTINCT EmpCode
            FROM ActiveUsers
            WHERE NAME_ NOT LIKE '%QC%' AND NAME_ NOT LIKE '%IPQC%'
        )
        SELECT 
            '{target_date}' as Date,
            (SELECT COUNT(*) FROM FilterUsers) as FilterActive,
            {expected[i]} as Expected
        """
        
        df = pd.read_sql(query, conn)
        results.append(df)
        match = "MATCH" if df.iloc[0]['FilterActive'] == expected[i] else f"DIFF: {df.iloc[0]['FilterActive'] - expected[i]}"
        print(f"Date {target_date}: FilterActive={df.iloc[0]['FilterActive']}, Expected={expected[i]} -> {match}")
        
    final_df = pd.concat(results)
    print("\n--- Results (No QC) ---")
    print(final_df.to_string(index=False))

if __name__ == "__main__":
    verify_no_qc_rule()
    conn.close()
