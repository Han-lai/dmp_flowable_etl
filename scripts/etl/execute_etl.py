#!/usr/bin/env python3
"""
DMP Flowable Data Pipeline Execution Script
Purpose: Sequentially execute SQL files to rebuild the Bronze/Silver/Gold architecture.

Features:
1. --skip-existing: Automatically skips if the target table already exists (safe mode).
2. --force: Automatically confirms all rebuild prompts (destructive mode).
3. --status: Displays current sync status and row counts.
"""
import clickhouse_connect
import os
import sys
import argparse
from pathlib import Path
import re
import pandas as pd

# =================================================================
# 1. Configuration
# =================================================================

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', '10.136.218.207'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8121')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'default'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

SQL_FILES = [
    ('01_bronze_flowable_core.sql', 'Bronze Layer 1 (Flowable Core)'),
    ('02_bronze_common_dims.sql', 'Bronze Layer 2 (Common Dimensions)'),
    ('03_silver_pivot_and_hierarchy.sql', 'Silver Layer 1 (Pivot + Hierarchy)'),
    ('04_silver_fact_tasks.sql', 'Silver Layer 2 (Core Fact Table)'),
    ('05_silver_dim_users.sql', 'Silver Layer 3 (User Dimension)'),
    ('06_gold_kpi_task_completion.sql', 'Gold Layer 1 (L5 Completion API)'),
    ('07_gold_kpi_user_utilization.sql', 'Gold Layer 2 (L7 User Utilization)'),
]

# =================================================================
# 2. Core Functions
# =================================================================

def get_client():
    return clickhouse_connect.get_client(**CH_CONFIG)

def initialize_databases(client):
    """Ensures all required databases exist."""
    print("\n[DB Init] Initializing Databases...")
    for db in ['bronze', 'silver', 'gold']:
        try:
            client.command(f"CREATE DATABASE IF NOT EXISTS {db}")
            print(f" - {db:10}: OK")
        except Exception as e:
            print(f" - {db:10}: Failed - {e}")

def show_status(client):
    """Displays sync progress and row counts."""
    print("\n" + "=" * 60)
    print("Current Sync Status")
    print("=" * 60)
    
    # Check watermark progress
    try:
        wm_sql = "SELECT table_name, last_sync_time, sync_time, row_count FROM bronze._sync_watermark FINAL ORDER BY table_name"
        res = client.query(wm_sql)
        if res.result_rows:
            df = pd.DataFrame(res.result_rows, columns=['Table', 'Last Source TS', 'Sync At', 'Rows'])
            print("\n[Watermark Tracking]")
            print(df.to_string(index=False))
        else:
            print("\n[Watermark] No sync records found.")
    except Exception as e:
        print(f"\n[Watermark] Failed to read: {e}")

    # Check key table row counts
    print("\n[Key Table Row Counts]")
    tables = [
        "bronze.bpm_act_hi_taskinst", "silver.fact_task_instance", "gold.kpi_l5_task_completion"
    ]
    for t in tables:
        try:
            count = client.command(f"SELECT count() FROM {t}")
            print(f" - {t:35}: {count:,} rows")
        except:
            print(f" - {t:35}: (Not created yet)")

def execute_sql_file(client, sql_file: Path, description: str, args):
    """Executes a single SQL file with support for auto-skip or force mode."""
    print(f"\n{'-'*60}")
    print(f"Preparing to execute: {sql_file.name} ({description})")
    
    sql_content = sql_file.read_text(encoding='utf-8')
    
    # Parse target tables
    pattern = re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|MATERIALIZED\s+VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)', re.IGNORECASE)
    tables = pattern.findall(sql_content)
    
    existing_tables = []
    for table in tables:
        try:
            if client.command(f"EXISTS TABLE {table}"):
                count = client.command(f"SELECT count() FROM {table}")
                existing_tables.append((table, count))
        except: pass
            
    if existing_tables:
        if args.skip_existing:
            print(f"Tables exist. Skipping due to --skip-existing flag.")
            return
        
        if not args.force:
            print(f"WARNING: The following tables already exist:")
            for table, count in existing_tables:
                print(f"   - {table}: {count:,} rows")
            response = input("\nAre you sure you want to recreate? (y/N): ").lower().strip()
            if response != 'y':
                print(f"Skipped: {sql_file.name}")
                return
        else:
            print(f"Tables exist. Recreating due to --force flag.")

    # Split and execute statements
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
    
    failures = 0
    for i, stmt in enumerate(statements, 1):
        if not stmt.strip() or stmt.strip().upper().startswith('SELECT'):
            continue
        try:
            client.command(stmt)
        except Exception as e:
            print(f"[{i}/{len(statements)}] Error: {e}")
            failures += 1
            continue
    
    if failures == 0:
        print(f"Completed: {sql_file.name} executed successfully.")
    else:
        print(f"Completed: {sql_file.name} executed with {failures} errors.")

def main():
    parser = argparse.ArgumentParser(description="DMP Flowable Data Pipeline Execution Tool")
    parser.add_argument("--skip-existing", action="store_true", help="Automatically skip if table exists (safe mode)")
    parser.add_argument("--force", action="store_true", help="Automatically confirm all rebuilds (destructive)")
    parser.add_argument("--status", action="store_true", help="Display sync progress and row counts only")
    
    args = parser.parse_args()
    
    print("="*60)
    print("DMP Flowable Execution Tool")
    print("="*60)
    
    try:
        client = get_client()
        client.query("SELECT 1")
    except Exception as e:
        print(f"ClickHouse connection failed: {e}")
        sys.exit(1)

    if args.status:
        show_status(client)
        return

    # Ensure Databases exist first
    initialize_databases(client)

    # Dynamic path resolution for sql directory
    script_dir = Path(__file__).resolve().parent
    sql_dir = script_dir.parent.parent / 'sql' / 'etl'
    
    for sql_file_name, description in SQL_FILES:
        sql_file = sql_dir / sql_file_name
        if sql_file.exists():
            execute_sql_file(client, sql_file, description, args)
        else:
            print(f"Warning: File not found {sql_file_name}")
    
    print("\n" + "="*60)
    print("All operations completed successfully!")
    print("="*60)

if __name__ == '__main__':
    main()
