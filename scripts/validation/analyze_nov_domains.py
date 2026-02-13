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

def analyze_nov_domains():
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
    expected_active = [14, 10, 9, 8, 9, 9, 1]
    
    print(f"{'Date':<12} | {'All_V3':<6} | {'Core_Only':<9} | {'Exp':<5}")
    print("-" * 50)
    
    for i, dt in enumerate(dates):
        target_date = dt.strftime('%Y-%m-%d')
        
        # Get All V3 Users
        q_all = f"""
        WITH {config_cte}
        SELECT COUNT(DISTINCT t.ASSIGNEE_) as Count
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.END_TIME_ IS NOT NULL AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
          AND t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
          AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
          AND v.TEXT_ = '{line}'
        """
        
        # Get Core V3 Users (3.5.2 or 3.5.3)
        q_core = f"""
        WITH {config_cte}
        SELECT COUNT(DISTINCT t.ASSIGNEE_) as Count
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.END_TIME_ IS NOT NULL AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
          AND (t.TASK_DEF_KEY_ LIKE 'V3_5_2_%%' OR t.TASK_DEF_KEY_ LIKE 'V3_5_3_%%')
          AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
          AND v.TEXT_ = '{line}'
        """
        
        c_all = pd.read_sql(q_all, conn).iloc[0]['Count']
        c_core = pd.read_sql(q_core, conn).iloc[0]['Count']
        exp = expected_active[i]
        
        print(f"{target_date:<12} | {c_all:<6} | {c_core:<9} | {exp:<5}")

if __name__ == "__main__":
    analyze_nov_domains()
    conn.close()
