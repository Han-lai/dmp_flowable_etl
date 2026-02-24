import pyodbc
import pandas as pd
import warnings
import sys

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

def analyze_dec_discrepancy():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    
    # User Provided Expected Counts
    user_expected = {
        '2025-12-25': 5,
        '2025-12-26': 9,
        '2025-12-27': 7,
        '2025-12-28': 1,
        '2025-12-29': 7,
        '2025-12-30': 12,
        '2025-12-31': 9
    }

    config_cte = f"""
    ConfigUsers AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    )
    """
    
    # Potential Quality Tasks to Exclude
    quality_tasks = [
        'V3_5_3_4_1', 'V3_5_3_9_1', 'V3_5_2_9_1', 'V3_5_2_5_2', 
        'V3_5_2_6_1', 'V3_5_2_1_13', 'V3_5_3_7_1', 'V3_5_3_10_1'
    ]

    print(f"{'Date':<12} | {'Exp':<5} | {'All':<5} | {'NoQE':<5} | {'Match?':<10} | {'Users Only In All (Excluded)'}")
    print("-" * 100)

    for d in dates:
        date_str = d.strftime('%Y-%m-%d')
        exp = user_expected.get(date_str, 0)
        
        conn = pyodbc.connect(conn_str)
        try:
            query = f"""
            WITH {config_cte}
            SELECT DISTINCT 
                t.ASSIGNEE_ as EmpCode,
                t.TASK_DEF_KEY_,
                v.TEXT_ as LineName,
                CASE WHEN c.EmpCode IS NOT NULL THEN 1 ELSE 0 END as IsConfigured
            FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v 
                ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
            LEFT JOIN ConfigUsers c ON t.ASSIGNEE_ = c.EmpCode
            WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
              AND CAST(t.END_TIME_ AS DATE) = '{date_str}'
              AND t.ASSIGNEE_ IS NOT NULL
              AND t.ASSIGNEE_ NOT LIKE 'DMPV%%'
            """
            
            df = pd.read_sql(query, conn)
            
            users_all = set()
            users_no_qe = set()
            
            for emp, group in df.groupby('EmpCode'):
                # Common "Trust LineName" Logic
                has_e5_task_all = any(group['LineName'] == 'E5')
                is_configured = group['IsConfigured'].iloc[0] == 1
                has_null_line_task = any(group['LineName'].isna())
                
                # Logic 1: Include ALL tasks
                if has_e5_task_all or (is_configured and has_null_line_task):
                    users_all.add(emp)
                
                # Logic 2: Exclude Quality Tasks
                # Filter group to Non-QE tasks only
                group_no_qe = group[~group['TASK_DEF_KEY_'].isin(quality_tasks)]
                if not group_no_qe.empty:
                    has_e5_task_no_qe = any(group_no_qe['LineName'] == 'E5')
                    has_null_line_task_no_qe = any(group_no_qe['LineName'].isna())
                    
                    if has_e5_task_no_qe or (is_configured and has_null_line_task_no_qe):
                        users_no_qe.add(emp)

            cnt_all = len(users_all)
            cnt_no_qe = len(users_no_qe)
            
            match_status = ""
            if cnt_all == exp: match_status = "All Match"
            elif cnt_no_qe == exp: match_status = "NoQE Match"
            else: match_status = "No Match"
            
            excluded_users = sorted(list(users_all - users_no_qe))
            
            print(f"{date_str:<12} | {exp:<5} | {cnt_all:<5} | {cnt_no_qe:<5} | {match_status:<10} | {excluded_users}")
            sys.stdout.flush()
            
        except Exception as e:
            print(f"Error for {date_str}: {e}")
            sys.stdout.flush()
        finally:
            conn.close()

if __name__ == "__main__":
    analyze_dec_discrepancy()
