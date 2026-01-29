import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "bronze"
}

def check_mdm_tables():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("Checking existing MDM tables in 'bronze' database...")
    result = client.query("SELECT name FROM system.tables WHERE database = 'bronze' AND name LIKE '%mdm%'")
    
    existing_tables = [row[0] for row in result.result_rows]
    print(f"Found {len(existing_tables)} MDM tables:")
    for table in existing_tables:
        print(f" - {table}")
        
    return existing_tables

if __name__ == "__main__":
    check_mdm_tables()
