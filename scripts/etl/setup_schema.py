#!/usr/bin/env python3
"""
DMP Flowable Data Pipeline - Infrastructure Setup Tool
Purpose: One-time setup of ClickHouse Databases and Table Schemas (Bronze/Silver/Gold).
Usage: Run this before the first ETL execution or when schema changes occur.
"""
import clickhouse_connect
import os
import sys
import argparse
import re
from pathlib import Path
import yaml

# =================================================================
# 1. Configuration
# =================================================================

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8122')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'default'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}


# ==========================================
# Load Infrastructure Configuration from YAML
# ==========================================
def load_infra_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config", "infra_config.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading infra configuration: {e}")
        sys.exit(1)

INFRA_CONFIG = load_infra_config()

# =================================================================
# 2. Functions
# =================================================================

def get_client():
    return clickhouse_connect.get_client(**CH_CONFIG)

def initialize_databases(client):
    print("\n[DB Init] Initializing Databases...")
    for db in INFRA_CONFIG.get('databases', []):
        try:
            client.command(f"CREATE DATABASE IF NOT EXISTS {db}")
            print(f" - {db:10}: OK")
        except Exception as e:
            print(f" - {db:10}: Failed - {e}")

def execute_sql_file(client, sql_file: Path, description: str, force=False):
    print(f"\n{'-'*60}")
    print(f"Deploying: {sql_file.name} ({description})")
    
    sql_content = sql_file.read_text(encoding='utf-8')
    
    # Simple parser to find table names in DDL
    pattern = re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|MATERIALIZED\s+VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)', re.IGNORECASE)
    tables = pattern.findall(sql_content)
    
    if not force:
        for table in tables:
            try:
                if client.command(f"EXISTS TABLE {table}"):
                    print(f"   ! Table {table} already exists. Use --force to recreate if needed.")
            except: pass

    # Execute statements sequentially
    statements = []
    current = []
    for line in sql_content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--'): continue
        current.append(line)
        if stripped.endswith(';'):
            stmt = '\n'.join(current).strip()
            if stmt and stmt != ';':
                statements.append(stmt)
            current = []
    
    success = 0
    for i, stmt in enumerate(statements, 1):
        if not stmt.strip() or stmt.strip().upper().startswith('SELECT'): continue
        try:
            client.command(stmt)
            success += 1
        except Exception as e:
            print(f"   [Error] Statement {i}: {e}")
    
    print(f"Successfully executed {success}/{len(statements)} statements.")

def main():
    parser = argparse.ArgumentParser(description="Infrastructure Setup Tool")
    parser.add_argument("--force", action="store_true", help="Force execution of DDLs even if tables exist")
    args = parser.parse_args()
    
    try:
        client = get_client()
        initialize_databases(client)
        
        script_dir = Path(__file__).resolve().parent
        sql_dir = script_dir.parent.parent / 'sql' / 'etl' / 'schema'
        
        for script in INFRA_CONFIG.get('setup_scripts', []):
            sql_file_name = script['file']
            description = script.get('desc', '') # Make desc optional
            sql_file = sql_dir / sql_file_name
            if sql_file.exists():
                execute_sql_file(client, sql_file, description, force=args.force)
            else:
                print(f"Warning: File not found {sql_file_name}")
                
        print("\n" + "="*60)
        print("Infrastructure setup complete. You can now run the ETL Pipeline.")
        print("="*60)
        
    except Exception as e:
        print(f"Setup Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
