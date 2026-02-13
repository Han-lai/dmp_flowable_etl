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

def verify_dec_with_s_or_e():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    expected = [5, 9, 7, 1, 7, 12, 9]
    
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
    
    print(f"=== Dec 25-31: Verification with 'Started or Ended' Rule ===")
    
    for i, dt in enumerate(dates):
        target_date = dt.strftime('%Y-%m-%d')
        
        # Using S_or_E + Core Domains (3.5.2-3)
        query = f"""
        WITH {config_cte},
        UserAllTasks AS (
            SELECT DISTINCT 
                t.ASSIGNEE_ as EmpCode,
                t.NAME_,
                t.TASK_DEF_KEY_
            FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
            JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
            WHERE (t.TASK_DEF_KEY_ LIKE 'V3_5_2_%%' OR t.TASK_DEF_KEY_ LIKE 'V3_5_3_%%')
              AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
              AND v.TEXT_ = '{line}'
              AND (CAST(t.START_TIME_ AS DATE) = '{target_date}' OR CAST(t.END_TIME_ AS DATE) = '{target_date}')
        )
        SELECT COUNT(DISTINCT EmpCode) as Count FROM UserAllTasks
        """
        
        count = pd.read_sql(query, conn).iloc[0]['Count']
        exp = expected[i]
        match = "✅" if count == exp else f"❌ ({count-exp})"
        print(f"{target_date}: Count={count}, Exp={exp} -> {match}")

if __name__ == "__main__":
    verify_dec_with_s_or_e()
    conn.close()
