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

def verify_dg3_st02():
    plant = 'DG3'
    factory = 'SMT'
    line = 'ST02'
    
    # Range 1: Nov 24 - Nov 30 (Previous Request)
    dates_nov = pd.date_range(start='2025-11-24', end='2025-11-30')
    exp_nov = {
        '2025-11-24': 16, '2025-11-25': 12, '2025-11-26': 11,
        '2025-11-27': 12, '2025-11-28': 11, '2025-11-29': 17,
        '2025-11-30': 5
    }
    
    # Range 2: Dec 25 - Dec 31 (New Request)
    dates_dec = pd.date_range(start='2025-12-25', end='2025-12-31')
    exp_dec = {
        '2025-12-25': 14,
        '2025-12-26': 13,
        '2025-12-27': 15,
        '2025-12-28': 5,
        '2025-12-29': 9,
        '2025-12-30': 13,
        '2025-12-31': 7
    }

    # Range 3: Oct 25 - Oct 31 (New Request)
    dates_oct = pd.date_range(start='2025-10-25', end='2025-10-31')
    exp_oct = {
        '2025-10-25': 11,
        '2025-10-26': 4,
        '2025-10-27': 13,
        '2025-10-28': 10,
        '2025-10-29': 6,
        '2025-10-30': 9,
        '2025-10-31': 10
    }

    # CTE for Configured Users
    config_cte = f"""
    ConfigUsers AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    )
    """

    print(f"{'Date':<12} | {'Exp':<5} | {'Act':<5} | {'Match':<5} | {'Included Users'}")
    print("-" * 120)

    # Combine all ranges
    all_dates = dates_nov.union(dates_dec).union(dates_oct)
    expected_counts = {**exp_nov, **exp_dec, **exp_oct}

    # Sort dates
    sorted_dates = sorted(all_dates)

    for d in sorted_dates:
        date_str = d.strftime('%Y-%m-%d')
        exp = expected_counts.get(date_str, 0)
        
        conn = pyodbc.connect(conn_str)
        try:
            # Main Audit Query
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
            
            included_users = set()
            for emp, group in df.groupby('EmpCode'):
                # Trust LineName Logic (Strict for Specific Line)
                has_target_line_task = any(group['LineName'] == line)
                is_configured = group['IsConfigured'].iloc[0] == 1
                has_null_line_task = any(group['LineName'].isna())
                
                include_user = False
                if has_target_line_task:
                    include_user = True
                elif is_configured: 
                     # Only fallback if they did tasks deemed "generic" (no line variable)
                     if has_null_line_task:
                         include_user = True
                
                if include_user:
                    included_users.add(emp)
            
            cnt = len(included_users)
            match = "YES" if cnt == exp else "NO"
            users_list = sorted(list(included_users))
            
            # Print only first few users
            users_disp = str(users_list[:5]) + "..." if len(users_list) > 5 else str(users_list)
            
            print(f"{date_str:<12} | {exp:<5} | {cnt:<5} | {match:<5} | {users_disp}")
            sys.stdout.flush()
            
        except Exception as e:
            print(f"Error for {date_str}: {e}")
            sys.stdout.flush()
        finally:
            conn.close()

if __name__ == "__main__":
    verify_dg3_st02()
