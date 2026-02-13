
import requests
import sys

host = "REDACTED_IP"
port = 8121
auth = ('default', 'default')

def check_tables():
    url = f"http://{host}:{port}/?query=SELECT%20database,name%20FROM%20system.tables"
    print(f"Querying {url}...")
    try:
        response = requests.get(url, auth=auth, timeout=10)
        if response.status_code == 200:
            print("Successfully retrieved tables.")
            all_tables = response.text.strip().split('\n')
            # Expected format: database<tab>name
            
            # Request list
            requested_tables = [
                "APP_SRV_BPM.dbo.ACT_HI_TASKINST",
                "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK",
                "APP_SRV_BPM.dbo.ACT_HI_VARINST",
                "APP_SRV_COMMON.dbo.HR_Employee",
                "APP_SRV_COMMON.dbo.EmpNodeRoleMapping",
                "APP_SRV_COMMON.dbo.EmpUserGroupMapping",
                "APP_SRV_COMMON.dbo.UserGroup",
                "APP_SRV_COMMON.dbo.EmpOrgInfoMapping",
                "APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER_0202",
                "APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER_0202",
                "APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER_0202",
                "APP_SRV_COMMON.dbo.ProcessRoleUserMapping",
                "APP_SRV_COMMON.dbo.DMPFunctionConfig",
                "APP_SRV_COMMON.dbo.DMPFunctionClientMapping"
            ]
            
            db_table_map = {}
            for line in all_tables:
                parts = line.split('\t')
                if len(parts) >= 2:
                    db = parts[0]
                    tbl = parts[1]
                    if db not in db_table_map:
                        db_table_map[db] = set()
                    db_table_map[db].add(tbl)
            
            print("\nMatching Results:")
            for req in requested_tables:
                # Parse user request: APP_SRV_BPM.dbo.ACT_HI_TASKINST
                # Assuming user means Database: APP_SRV_BPM, Table: ACT_HI_TASKINST (ignoring dbo or maybe dbo is schema/part of name)
                
                parts = req.split('.')
                # If 3 parts: DB.Schema.Table
                # If 2 parts: DB.Table
                
                found = False
                potential_db = parts[0]
                potential_table = parts[-1] 
                
                # Check direct match DB=APP_SRV_BPM, Table=ACT_HI_TASKINST
                if potential_db in db_table_map and potential_table in db_table_map[potential_db]:
                     print(f"[FOUND] {req} -> Database: {potential_db}, Table: {potential_table}")
                     found = True
                
                # Check distinct "dbo" handling if applicable (e.g. table name is dbo.ACT_HI_TASKINST)
                if not found and potential_db in db_table_map:
                    # Check if table name contains 'dbo.'
                    for t in db_table_map[potential_db]:
                        if t == f"dbo.{potential_table}" or t == potential_table:
                             print(f"[FOUND] {req} -> Database: {potential_db}, Table: {potential_table} (Match found as {t})")
                             found = True
                             break
                
                # Check loose match
                if not found:
                    # Search all DBs for table name
                    matches = []
                    found_exact_in_other_db = False
                    
                    # Fuzzy search for missing MDM tables
                    fuzzy_matches = []
                    
                    for db, tables in db_table_map.items():
                        if potential_table in tables:
                            matches.append(f"{db}.{potential_table}")
                            found_exact_in_other_db = True
                        
                        # Check for partial matches if distinct not found
                        if "MDM" in potential_table:
                             base_name = potential_table.replace("_0202", "")
                             for t in tables:
                                 if base_name in t:
                                     fuzzy_matches.append(f"{db}.{t}")

                    if found_exact_in_other_db:
                        print(f"[PARTIAL] {req} found in other databases: {', '.join(matches)}")
                    elif fuzzy_matches:
                        print(f"[MISSING] {req} - Found similar tables: {', '.join(fuzzy_matches)}")
                    else:
                        print(f"[MISSING] {req}")


            print("\n--- Detailed Search ---")
            
            # List all tables in 'bronze' database
            if 'bronze' in db_table_map:
                print(f"\nTables in 'bronze' database: {len(db_table_map['bronze'])}")
                for t in sorted(db_table_map['bronze']):
                    print(f"  - {t}")
            else:
                print("\n'bronze' database not found or empty.")

            # List all tables containing 'MDM'
            print("\nAll tables containing 'MDM':")
            mdm_found = False
            for db, tables in db_table_map.items():
                for t in tables:
                    if "MDM" in t:
                        print(f"  - {db}.{t}")
                        mdm_found = True
            if not mdm_found:
                print("  (None found)")

            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error connecting: {e}")

if __name__ == "__main__":
    check_tables()
