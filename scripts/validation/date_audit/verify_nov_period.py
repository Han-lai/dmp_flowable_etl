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

def verify_nov_period():
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
    
    dates = pd.date_range(start='2025-11-24', end='2025-11-30')
    # User provided 8 values for 7 days: 14|10|9|8|9|9|9|1
    # Assuming the first total or typo, let's map:
    # 24(Mon): 14
    # 25(Tue): 10
    # 26(Wed): 9
    # 27(Thu): 8
    # 28(Fri): 9
    # 29(Sat): 9
    # 30(Sun): 1
    # (The extra 9 in 14|10|9|8|9|9|9|1 might be a typo or 8th value)
    expected_active = [14, 10, 9, 8, 9, 9, 1] 
    
    results = []
    
    print(f"{'Date':<12} | {'Day':<10} | {'Result':<6} | {'Expected':<8} | {'Status'}")
    print("-" * 60)
    
    for i, dt in enumerate(dates):
        target_date = dt.strftime('%Y-%m-%d')
        day_name = dt.day_name()
        
        # Rule: Saturday(5) and Sunday(6) are non-workdays
        is_weekend = dt.weekday() >= 5
        
        # NOTE: For Nov, no known broad holidays like Dec 25.
        # So we use the "Weekend" logic for QC/QE exclusion.
        
        query = f"""
        WITH {config_cte},
        UserAllTasks AS (
            SELECT DISTINCT 
                t.ASSIGNEE_ as EmpCode,
                t.NAME_,
                t.TASK_DEF_KEY_
            FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
            JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v 
                ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
            WHERE t.END_TIME_ IS NOT NULL 
                AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
                AND t.TASK_DEF_KEY_ LIKE 'V3_5_[23]_%%'
                AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
                AND v.TEXT_ = '{line}'
        ),
        UserCoreTaskCount AS (
            SELECT 
                EmpCode,
                COUNT(*) as TotalTasks,
                SUM(CASE WHEN (NAME_ LIKE '%%QC%%' OR NAME_ LIKE '%%IPQC%%' OR TASK_DEF_KEY_ LIKE 'V3_5_3_10%%') THEN 1 ELSE 0 END) as QualityTaskCount
            FROM UserAllTasks
            GROUP BY EmpCode
        ),
        FinalActiveUsers AS (
            SELECT EmpCode
            FROM UserCoreTaskCount
            WHERE 1=1
            { "AND (TotalTasks > QualityTaskCount)" if is_weekend else "" }
        )
        SELECT COUNT(*) as Count FROM FinalActiveUsers
        """
        
        df = pd.read_sql(query, conn)
        count = df.iloc[0]['Count']
        
        exp = expected_active[i] if i < len(expected_active) else "???"
        status = "✅ MATCH" if count == exp else f"❌ DIFF ({count-exp if isinstance(exp, int) else '?'})"
        
        print(f"{target_date:<12} | {day_name:<10} | {count:<6} | {exp:<8} | {status}")
        results.append({'Date': target_date, 'Count': count, 'Expected': exp})

    # Also verify Config User (should be 57)
    df_conf = pd.read_sql(f"WITH {config_cte} SELECT COUNT(*) as Count FROM ConfigUsers", conn)
    print(f"\nConfig User Count: {df_conf.iloc[0]['Count']} (Expected: 57)")

if __name__ == "__main__":
    verify_nov_period()
    conn.close()
