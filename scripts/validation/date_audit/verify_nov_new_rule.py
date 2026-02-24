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

def verify_nov_new_rule():
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
        WHERE NodeCode LIKE '%%V3_%%'
    ),
    V3ConfigMembers AS (
        SELECT EmpCode FROM V3Members
        WHERE EmpCode IN (SELECT EmpCode FROM ConfigUsers)
    )
    """
    
    dates = pd.date_range(start='2025-11-24', end='2025-11-30')
    # Alignment: 24(14), 25(10), 26(9), 27(8), 28(9), 29(9), 30(1)
    expected = [14, 10, 9, 8, 9, 9, 1]
    
    print(f"{'Date':<12} | {'S_or_E_All':<12} | {'S_or_E_Core':<12} | {'Exp':<5} | {'Stat'}")
    print("-" * 65)
    
    for i, dt in enumerate(dates):
        target_date = dt.strftime('%Y-%m-%d')
        
        # Rule: Started or Ended Today
        # Try both All(1-4) and Core(2-3)
        
        def get_count(domains_clause):
            q = f"""
            WITH {config_cte},
            ActiveUsers AS (
                SELECT DISTINCT t.ASSIGNEE_ as EmpCode
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
                WHERE {domains_clause}
                  AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
                  AND v.TEXT_ = '{line}'
                  AND (CAST(t.START_TIME_ AS DATE) = '{target_date}' OR CAST(t.END_TIME_ AS DATE) = '{target_date}')
            )
            SELECT COUNT(*) as Count FROM ActiveUsers
            """
            return pd.read_sql(q, conn).iloc[0]['Count']

        c_all = get_count("t.TASK_DEF_KEY_ LIKE 'V3_5_%%'")
        c_core = get_count("(t.TASK_DEF_KEY_ LIKE 'V3_5_2_%%' OR t.TASK_DEF_KEY_ LIKE 'V3_5_3_%%')")
        
        exp = expected[i]
        match = "✅" if (c_all == exp or c_core == exp) else "❌"
        
        print(f"{target_date:<12} | {c_all:<12} | {c_core:<12} | {exp:<5} | {match}")

if __name__ == "__main__":
    verify_nov_new_rule()
    conn.close()
