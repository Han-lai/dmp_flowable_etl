#!/usr/bin/env python3
import clickhouse_connect
import sys
import os

CLICKHOUSE_CONFIG = {
    "host": os.getenv("CLICKHOUSE_HOST", "REDACTED_IP"),
    "port": int(os.getenv("CLICKHOUSE_PORT", "8121")),
    "username": os.getenv("CLICKHOUSE_USERNAME", "default"),
    "password": os.getenv("CLICKHOUSE_PASSWORD", "default"),
    "database": os.getenv("CLICKHOUSE_DATABASE", "default")
}

def execute_sql_file(filepath):
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    print(f"Executing {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Split by semicolon but ignore inside quotes/comments if possible
    # For simplicity, we use the multiquery capability of the raw client if available
    # but the python client usually expects better handling.
    # However, many rebuild scripts are mostly single statement DDLs or separate blocks.
    
    statements = sql.split(';')
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            print(f"Running statement starting with: {stmt[:50]}...")
            client.command(stmt)
        except Exception as e:
            print(f"Error in statement: {e}")
            if "MATERIALIZED VIEW" in stmt and "already exists" in str(e).lower():
                print("Skipping already exists error...")
                continue
            # Some errors might be fatal
            # sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python execute_sql.py <file1> <file2> ...")
        sys.exit(1)
    
    for arg in sys.argv[1:]:
        execute_sql_file(arg)
