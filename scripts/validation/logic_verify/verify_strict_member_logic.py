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

def verify_strict_member_logic():
    # Target: WJ2 NBU E5
    # Dates with High Counts: Nov 24 (16 vs 14), Nov 29 (14 vs 9), Dec 30 (17 vs 12)
    dates = ['2025-11-24', '2025-11-29', '2025-12-30']
    
    print(f"{'Date':<12} | {'User':<10} | {'Groups':<40} | {'NodeCodes':<40} | {'Strict V3 Member?'}")
    print("-" * 120)

    for date_str in dates:
        conn = pyodbc.connect(conn_str)
        try:
            # 1. Get Active Users (LineName Logic + Quality Included)
            query_active = f"""
            SELECT DISTINCT t.ASSIGNEE_ as EmpCode
            FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v 
                ON t.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'lineName'
            LEFT JOIN APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202 c 
                ON t.ASSIGNEE_ = c.EmpCode AND c.LineName IN ('E5', '*') AND c.Plant='WJ2' AND c.Factory='NBU'
            WHERE t.TASK_DEF_KEY_ LIKE 'V3_5_%%'
              AND CAST(t.END_TIME_ AS DATE) = '{date_str}'
              AND t.ASSIGNEE_ IS NOT NULL
              AND t.ASSIGNEE_ NOT LIKE 'DMPV%%'
              AND (v.TEXT_ = 'E5' OR (v.TEXT_ IS NULL AND c.EmpCode IS NOT NULL))
            """
            df_active = pd.read_sql(query_active, conn)
            active_users = df_active['EmpCode'].tolist()
            
            if not active_users:
                print(f"{date_str:<12} | No active users found")
                continue

            users_str = "', '".join(active_users)
            
            # 2. Get User Groups
            query_groups = f"""
            SELECT m.EmpCode, g.UserGroupName
            FROM APP_SRV_COMMON.dbo.EmpUserGroupMapping_0202 m
            JOIN APP_SRV_COMMON.dbo.UserGroup_0202 g ON m.UserGroupId = g.UserGroupId
            WHERE m.EmpCode IN ('{users_str}')
            """
            df_groups = pd.read_sql(query_groups, conn)
            
            # 3. Get Node Codes
            query_nodes = f"""
            SELECT EmpCode, NodeCode
            FROM APP_SRV_COMMON.dbo.EmpNodeRoleMapping_0202
            WHERE EmpCode IN ('{users_str}')
            """
            df_nodes = pd.read_sql(query_nodes, conn)
            
            # Check Logic
            valid_active_count = 0
            
            for u in active_users:
                # Groups
                groups = df_groups[df_groups['EmpCode'] == u]['UserGroupName'].tolist()
                groups_str = ",".join(groups) if groups else "None"
                
                # Nodes
                nodes = df_nodes[df_nodes['EmpCode'] == u]['NodeCode'].tolist()
                nodes_str = ",".join(nodes) if nodes else "None"
                
                # Strict Rule: 
                # 1. Must have V3 Node
                has_v3_node = any('V3' in n for n in nodes)
                
                # 2. Must be User Group "User", and NOT any Excluded group
                # Excluded: ManagerUser, LocalAdmin, GlobalAdmin, SystemAdmin, InternalAudit, SeniorOfficers&DTO
                # Whitelist for V3: ONLY "User"? The rule says: "UserGroupNames = 'User'".
                # It says "Only filter completely matching 'UserGroupNames = User'". 
                # Does it mean if I have "User" AND "ManagerUser", I am excluded? 
                # Text: "If identity contains other identities, also need to exclude". -> YES. STRICT.
                
                is_strict_user = False
                if 'User' in groups:
                    others = [g for g in groups if g != 'User']
                    if not others:
                        is_strict_user = True
                    else:
                        # Check if others are harmless? Rule says "If contains other identity... exclude".
                        # Let's list the others to see.
                        is_strict_user = False 
                
                is_valid = has_v3_node and is_strict_user
                valid_str = "YES" if is_valid else "NO"
                
                if is_valid: valid_active_count +=1
                
                print(f"{date_str:<12} | {u:<10} | {groups_str:<40} | {nodes_str[:40]:<40} | {valid_str}")
            
            print(f"Total Active (Action): {len(active_users)}, Valid Active (Strict): {valid_active_count}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    verify_strict_member_logic()
