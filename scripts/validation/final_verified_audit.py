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

def get_strict_v3_members(conn, emp_codes):
    if not emp_codes:
        return set()
    
    users_str = "', '".join(emp_codes)
    
    # 1. Check Node Codes (Must have V3)
    query_nodes = f"""
    SELECT EmpCode, NodeCode
    FROM APP_SRV_COMMON.dbo.EmpNodeRoleMapping_0202
    WHERE EmpCode IN ('{users_str}')
    """
    df_nodes = pd.read_sql(query_nodes, conn)
    
    # 2. Check User Groups (Must be strictly 'User')
    query_groups = f"""
    SELECT m.EmpCode, g.UserGroupName
    FROM APP_SRV_COMMON.dbo.EmpUserGroupMapping_0202 m
    JOIN APP_SRV_COMMON.dbo.UserGroup_0202 g ON m.UserGroupId = g.UserGroupId
    WHERE m.EmpCode IN ('{users_str}')
    """
    df_groups = pd.read_sql(query_groups, conn)
    
    valid_members = set()
    
    for emp in emp_codes:
        # Node Logic: Must have at least one V3 node
        user_nodes = df_nodes[df_nodes['EmpCode'] == emp]['NodeCode'].fillna('').tolist()
        has_v3_node = any('V3' in node for node in user_nodes)
        
        # Group Logic: Must contain 'User' AND NOT contain any restricted roles
        # Restricted roles essentially mean anything other than 'User' for V3 context?
        # User said: "If identity contains other identities, also need to exclude"
        # So essentially: set(groups) == {'User'}? Or is 'User' + 'SomethingHarmless' allowed?
        # Based on previous analysis (PowerUser excluded), let's be strict:
        # Allow 'User'. Disallow 'PowerUser', 'ManagerUser', etc.
        # What if they have 'User' and 'FactoryUser'? 
        # Let's assume STRICT equality to ['User'] for now based on "Exclude if contains other identity".
        
        user_groups = df_groups[df_groups['EmpCode'] == emp]['UserGroupName'].fillna('').tolist()
        
        # Filter out empty strings if any
        user_groups = [g for g in user_groups if g]
        
        is_strict_user = False
        if 'User' in user_groups:
            # Check if there are other groups
            other_groups = [g for g in user_groups if g != 'User']
            if not other_groups:
                is_strict_user = True
            else:
                 # If they have other groups, are they allowed?
                 # For V3 config: "Only filter completely matching UserGroupNames = User"
                 # And "If identity contains other identities, also need to exclude"
                 is_strict_user = False
        
        if has_v3_node and is_strict_user:
            valid_members.add(emp)
            
    return valid_members

def run_audit(scope_name, plant, factory, line, dates, expected_counts):
    print(f"\n=== Audit Scope: {scope_name} ({plant}/{factory}/{line}) ===")
    print(f"{'Date':<12} | {'Exp':<5} | {'Act':<5} | {'Strict':<6} | {'Match':<5} | {'Diff Analysis'}")
    print("-" * 100)
    
    # CTE for Configured Users (Fallback)
    config_cte = f"""
    ConfigUsers AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('{line}', '*')
    )
    """
    
    for date_str, exp in expected_counts.items():
        conn = pyodbc.connect(conn_str)
        try:
            # 1. Get Potential Active Users (Action-based)
            # Trust LineName Logic implemented here
            query = f"""
            WITH {config_cte}
            SELECT DISTINCT 
                t.ASSIGNEE_ as EmpCode,
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
            
            potential_users = set()
            for emp, group in df.groupby('EmpCode'):
                has_target_line = any(group['LineName'] == line)
                is_configured = group['IsConfigured'].iloc[0] == 1
                has_null_line = any(group['LineName'].isna())
                
                if has_target_line:
                    potential_users.add(emp)
                elif is_configured and has_null_line:
                    potential_users.add(emp)
            
            action_count = len(potential_users)
            
            # 2. Apply Strict Member Logic
            strict_users = get_strict_v3_members(conn, list(potential_users))
            strict_count = len(strict_users)
            
            match = "YES" if strict_count == exp else "NO"
            
            # Diff Analysis
            excluded_count = action_count - strict_count
            diff_msg = f"Excluded {excluded_count} non-strict" if excluded_count > 0 else "-"
            
            print(f"{date_str:<12} | {exp:<5} | {action_count:<5} | {strict_count:<6} | {match:<5} | {diff_msg}")
            sys.stdout.flush()
            
        except Exception as e:
            print(f"Error for {date_str}: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    # 1. WJ2 NBU E5 (Nov 24-30)
    audit_wj2_nov = {
        '2025-11-24': 14, '2025-11-25': 10, '2025-11-26': 9, '2025-11-27': 8,
        '2025-11-28': 9, '2025-11-29': 9, '2025-11-30': 1
    }
    run_audit("WJ2 Nov", 'WJ2', 'NBU', 'E5', [], audit_wj2_nov)

    # 2. WJ2 NBU E5 (Dec 25-31)
    audit_wj2_dec = {
        '2025-12-25': 5, '2025-12-26': 9, '2025-12-27': 7, '2025-12-28': 1,
        '2025-12-29': 7, '2025-12-30': 12, '2025-12-31': 9
    }
    run_audit("WJ2 Dec", 'WJ2', 'NBU', 'E5', [], audit_wj2_dec)

    # 3. DG3 SMT ST02 (Oct 25-31)
    audit_dg3_oct = {
        '2025-10-25': 11, '2025-10-26': 4, '2025-10-27': 13, '2025-10-28': 10,
        '2025-10-29': 6, '2025-10-30': 9, '2025-10-31': 10
    }
    run_audit("DG3 Oct", 'DG3', 'SMT', 'ST02', [], audit_dg3_oct)

    # 4. DG3 SMT ST02 (Nov 24-30)
    audit_dg3_nov = {
        '2025-11-24': 16, '2025-11-25': 12, '2025-11-26': 11, '2025-11-27': 12,
        '2025-11-28': 11, '2025-11-29': 17, '2025-11-30': 5
    }
    run_audit("DG3 Nov", 'DG3', 'SMT', 'ST02', [], audit_dg3_nov)

    # 5. DG3 SMT ST02 (Dec 25-31)
    audit_dg3_dec = {
        '2025-12-25': 14, '2025-12-26': 13, '2025-12-27': 15, '2025-12-28': 5,
        '2025-12-29': 9, '2025-12-30': 13, '2025-12-31': 7
    }
    run_audit("DG3 Dec", 'DG3', 'SMT', 'ST02', [], audit_dg3_dec)
