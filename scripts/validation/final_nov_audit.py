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

def final_nov_done_qe_audit():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    # Range: Nov 24 - Dec 31
    dates = pd.date_range(start='2025-11-24', end='2025-12-31')
    
    expected_counts = {
        '2025-11-24': 14,
        '2025-11-25': 10,
        '2025-11-26': 9,
        '2025-11-27': 8,
        '2025-11-28': 9,
        '2025-11-29': 9,
        '2025-11-30': 1
    }

    # CTE for Configured Users (Fallback)
    config_cte = f"""
    ConfigUsers AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    )
    """
    
    # Exclude Quality Tasks? User said NO exclusion.
    # quality_tasks = [] 

    print(f"{'Date':<12} | {'Exp':<5} | {'Act':<5} | {'Match':<5} | {'Included Users'}")
    print("-" * 120)

    for d in dates:
        date_str = d.strftime('%Y-%m-%d')
        exp = expected_counts.get(date_str, 'N/A')
        
        # Robust connection handling: Open per query
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
            """
            
            df = pd.read_sql(query, conn)
            
            included_users = set()
            
            # Logic: Trust LineName='E5' OR Fallback to Config if LineName is missing
            for emp, group in df.groupby('EmpCode'):
                has_e5_task = any(group['LineName'] == 'E5')
                is_configured = group['IsConfigured'].iloc[0] == 1
                
                include_user = False
                
                if has_e5_task:
                    include_user = True
                elif is_configured:
                     # Check if there are any tasks with NULL LineName or where LineName is NOT for another specific line?
                     # Simple logic: If configured, and they did work that likely belongs to their line (implied by NULL lineName).
                     # Use strict NULL check for safety.
                     has_null_line_task = any(group['LineName'].isna())
                     if has_null_line_task:
                         include_user = True
                
                if include_user:
                    included_users.add(emp)
            
            cnt = len(included_users)
            
            match = ""
            if exp != 'N/A':
                match = "YES" if cnt == exp else "NO"
            else:
                match = "-"
                
            users_list = sorted(list(included_users))
            
            print(f"{date_str:<12} | {str(exp):<5} | {cnt:<5} | {match:<5} | {users_list}")
            
        except Exception as e:
            print(f"Error for {date_str}: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    # Redirect stdout to a file
    output_file = 'd:/kiro/dmp_flowable/audit_result_nov_dec.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        sys.stdout = f
        final_nov_done_qe_audit()
