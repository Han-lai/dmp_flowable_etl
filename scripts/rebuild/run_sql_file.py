import clickhouse_connect
import sys
import os

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_sql_file.py <path_to_sql_file>")
        sys.exit(1)
        
    sql_file = sys.argv[1]
    
    if not os.path.exists(sql_file):
        print(f"File not found: {sql_file}")
        sys.exit(1)
        
    print(f"Executing {sql_file}...")
    
    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        # Split by semicolon to handle multiple statements?
        # clickhouse-connect usually handles one statement per call, or script execution?
        # Best to split manually if it contains multiple statements.
        
        statements = sql_content.split(';')
        
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
                
            print(f"Running statement: {stmt[:50]}...")
            try:
                client.command(stmt)
            except Exception as e:
                print(f"Error executing statement: {e}")
                # Don't exit, try next statement (e.g. DROP might fail if not exists)
                
        print("Execution complete.")
        
    except Exception as e:
        print(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
