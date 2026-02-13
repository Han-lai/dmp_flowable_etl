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

def full_nov_audit():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    dates = pd.date_range(start='2025-11-24', end='2025-11-30')
    expected = [14, 10, 9, 8, 9, 9, 1]
    
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
    
    print(f"{'Date':<12} | {'Exp':<5} | {'All':<4} | {'Core':<5} | {'Core-QE':<8} | {'All-QE':<8}")
    print("-" * 60)
    
    for i, dt in enumerate(dates):
        target_date = dt.strftime('%Y-%m-%d')
        
        # Base data for done tasks
        q = f"""
        WITH {config_cte}
        SELECT 
            t.ASSIGNEE_ as EmpCode,
            t.TASK_DEF_KEY_
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
        WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
          AND v.TEXT_ = '{line}'
          AND (CAST(t.START_TIME_ AS DATE) = '{target_date}' OR CAST(t.END_TIME_ AS DATE) = '{target_date}')
          AND t.ASSIGNEE_ IN (SELECT EmpCode FROM V3ConfigMembers)
        """
        # Note: I'm using S_or_E here because 11/25 Tue (10) requires it.
        
        df = pd.read_sql(q, conn)
        
        users_all = df['EmpCode'].nunique()
        
        def filter_users(df_sub, core_only, exclude_qe):
            u_list = []
            for u in df_sub['EmpCode'].unique():
                tasks = df_sub[df_sub['EmpCode'] == u]['TASK_DEF_KEY_'].tolist()
                
                # Domain check
                if core_only:
                    has_core = any(k.startswith('V3_5_2') or k.startswith('V3_5_3') for k in tasks)
                    if not has_core: continue
                
                # QE check
                if exclude_qe:
                    only_qe = all(k.startswith('V3_5_3_10') or 'QC' in k or 'IPQC' in k for k in tasks)
                    if only_qe: continue
                
                u_list.append(u)
            return len(u_list)

        cnt_core = filter_users(df, True, False)
        cnt_core_qe = filter_users(df, True, True)
        cnt_all_qe = filter_users(df, False, True)
        
        print(f"{target_date:<12} | {expected[i]:<5} | {users_all:<4} | {cnt_core:<5} | {cnt_core_qe:<8} | {cnt_all_qe:<8}")

if __name__ == "__main__":
    full_nov_audit()
    conn.close()
