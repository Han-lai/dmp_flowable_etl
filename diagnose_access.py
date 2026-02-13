
import clickhouse_connect

def main():
    config = {
        "host": "REDACTED_IP",
        "port": 8121,
        "username": "default",
        "password": "default",
        "database": "default"
    }

    try:
        client = clickhouse_connect.get_client(**config)
        print("Connected.")
        
        # 1. Get all columns in system.users
        print("\n--- Columns in system.users ---")
        cols = client.query("DESCRIBE TABLE system.users").result_rows
        col_names = [c[0] for c in cols]
        print(col_names)
        
        # 2. Check for access_management related columns
        am_cols = [c for c in col_names if 'access' in c or 'management' in c or 'grant' in c]
        print(f"\nPotential access columns: {am_cols}")
        
        # 3. Query the default user
        if 'access_management' in col_names:
            print("\n--- Querying access_management for default ---")
            res = client.query(f"SELECT name, access_management FROM system.users WHERE name = 'default'").result_rows
            for row in res:
                print(f"User: {row[0]}, AccessManagement: {row[1]}")
        
        if 'grantees_any' in col_names:
             print("\n--- Querying grantees_any for default ---")
             res = client.query(f"SELECT name, grantees_any FROM system.users WHERE name = 'default'").result_rows
             for row in res:
                 print(f"User: {row[0]}, GranteesAny: {row[1]}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
