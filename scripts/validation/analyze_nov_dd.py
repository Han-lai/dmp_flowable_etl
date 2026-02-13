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

def analyze_nov_done_doing():
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
    # Use the 7 logical values from Jan's list
    expected_active = [14, 10, 9, 8, 9, 9, 1]
    
    print(f"{'Date':<12} | {'Done_Only':<9} | {'Done+Doing':<11} | {'Exp':<5}")
    print("-" * 55)
    
    for i, dt in enumerate(dates):
        target_date = dt.strftime('%Y-%m-%d')
        
        # Done Only (All V3)
        q_done = f"""
        WITH {config_cte}
        SELECT COUNT(DISTINCT t.ASSIGNEE_) as Count
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
          AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
          AND v.TEXT_ = '{line}'
          AND CAST(t.END_TIME_ AS DATE) = '{target_date}'
        """
        
        # Done + Doing (All V3)
        q_dd = f"""
        WITH {config_cte}
        SELECT COUNT(DISTINCT t.ASSIGNEE_) as Count
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
          AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
          AND v.TEXT_ = '{line}'
          AND (
            CAST(t.END_TIME_ AS DATE) = '{target_date}'
            OR (CAST(t.START_TIME_ AS DATE) <= '{target_date}' AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{target_date}'))
          )
        """
        
        c_done = pd.read_sql(q_done, conn).iloc[0]['Count']
        c_dd = pd.read_sql(q_dd, conn).iloc[0]['Count']
        exp = expected_active[i]
        
        print(f"{target_date:<12} | {c_done:<9} | {c_dd:<11} | {exp:<5}")

if __name__ == "__main__":
    analyze_nov_done_doing()
    conn.close()
