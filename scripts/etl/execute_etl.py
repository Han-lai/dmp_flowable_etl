#!/usr/bin/env python3
"""
DMP Flowable Data Pipeline Execution Script
Purpose: Sequentially execute SQL files to rebuild the Bronze/Silver/Gold architecture.

Features:
1. --skip-existing: Automatically skips if the target table already exists (safe mode).
2. --force: Automatically confirms all rebuild prompts (destructive mode).
3. --status: Displays current sync status and row counts.
4. --backfill: Computes the entire Silver and Gold historical data using safe 10-day time-chunked batching.
5. --low-ram: Enhances timeout and memory limits for low-end VMs during heavy operations.
"""
import clickhouse_connect
import os
import sys
import argparse
import time
import datetime
from pathlib import Path
import re
import pandas as pd

# =================================================================
# 1. Configuration
# =================================================================

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8121')), # Optional override
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
    # ('07_gold_kpi_user_utilization.sql', 'Gold Layer 2 (L7 User Utilization)'),
]

# =================================================================
# 2. Core Functions
# =================================================================

def get_client(is_low_ram=False):
    config = CH_CONFIG.copy()
    if is_low_ram:
        config['send_receive_timeout'] = 300
    return clickhouse_connect.get_client(**config)

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

    print("\n[Key Table Row Counts]")
    tables = [
        "bronze.bpm_act_hi_taskinst", 
        "silver.mv_varinst_pivoted",
        "silver.mv_fact_task_vx", 
        "gold.rmv_l5_task_completion_data_phys"
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

def load_sql_template(template_name):
    """Load SQL template from sql_templates directory."""
    script_dir = Path(__file__).resolve().parent
    template_path = script_dir.parent.parent / 'sql' / 'etl' / 'dml' / template_name
    return template_path.read_text(encoding='utf-8')

def execute_unified_computation_pipeline(client, args):
    """Core Engine for Safe Low-RAM Time-Bounded Computing."""
    print("\n" + "="*80)
    print(f"🚀 [ Unified Computation Engine ] Initiating Native Analytical Pipeline")
    print("="*80)
    
    if args.low_ram:
        client.command("SET max_threads = 1")
        client.command("SET max_memory_usage = 6000000000")
        client.command("SET max_bytes_before_external_group_by = 3000000000")
        client.command("SET join_algorithm = 'auto'")
        print("💡 Enabled Strict Mem-Bounds (max_memory_usage=6GB, auto join_algorithm)")

    # -------------------------------------------------------------------
    # Phase 1: Dimension Pivot (100% preparation before Tasks)
    # -------------------------------------------------------------------
    print("\n[Phase 1/4] Preparing Dimension Table: silver.mv_varinst_pivoted")
    try:
        client.command("TRUNCATE TABLE IF EXISTS silver.mv_varinst_pivoted")
    except Exception as e:
        print(f"   ⚠️ TRUNCATE failed (fallback to DROP): {e}")
        client.command("DROP TABLE IF EXISTS silver.mv_varinst_pivoted")
    
    pivot_sql = load_sql_template('backfill_pivot.sql')
    try:
        client.command(pivot_sql)
        print("   ✅ Populated successfully from Bronze.")
    except Exception as e:
        print(f"   ❌ Pivot population failed: {e}")
        sys.exit(1)

    print("\n[Phase 2/4] Optimizing Dimensions (Eliminating Cartesian Product Risks)...")
    client.command("OPTIMIZE TABLE silver.mv_varinst_pivoted FINAL")
    print("   ✅ Optimization complete.")

    # -------------------------------------------------------------------
    # Phase 3: Prepare Fact Tables
    # -------------------------------------------------------------------
    print("\n[Phase 3/4] Truncating Downstream Analytical Tables (Silver/Gold)...")
    try:
        client.command("TRUNCATE TABLE IF EXISTS silver.mv_fact_task_vx")
        client.command("TRUNCATE TABLE IF EXISTS gold.rmv_l5_task_completion_data_phys")
    except Exception as e:
        print(f"   ⚠️ TRUNCATE failed (fallback to DROP): {e}")
        client.command("DROP TABLE IF EXISTS silver.mv_fact_task_vx")
        client.command("DROP TABLE IF EXISTS gold.rmv_l5_task_completion_data_phys")

    print("   ✅ Silver and Gold tables are now ready (Truncated/Dropped).")

    # -------------------------------------------------------------------
    # Phase 4: Time-Chunked Loop Calculation
    # -------------------------------------------------------------------
    start_dateobj = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
    end_dateobj = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    
    windows = []
    # Add an Ancient Catch-all to make sure we don't drop tasks with empty or historical start times
    ancient_bound = start_dateobj - datetime.timedelta(days=1)
    windows.append(("1970-01-01", ancient_bound.strftime("%Y-%m-%d")))
    
    # Generate the iterative windows
    curr = start_dateobj
    while curr <= end_dateobj:
        next_curr = curr + datetime.timedelta(days=args.step_days)
        e = next_curr - datetime.timedelta(days=1)
        windows.append((curr.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")))
        curr = next_curr

    print("\n[Phase 4/4] Starting Bounded Chunk Execution Loop...")
    
    # Load SQL templates once
    silver_template = load_sql_template('backfill_silver.sql')
    exclusion_sql = load_sql_template('backfill_exclusion.sql')
    gold_template = load_sql_template('backfill_gold.sql')
    
    for (start_str, end_str) in windows:
        print(f"\n---- [Time Window: {start_str} ~ {end_str}] ----")
        
        # A. Ingest Silver
        insert_silver_sql = silver_template.replace('{start_date}', start_str).replace('{end_date}', end_str)
        try:
            client.command(insert_silver_sql)
            print(f"   ► (Silver) Data successfully computed and isolated.")
        except Exception as e:
            print(f"   ❌ Silver Compute FAILED: {str(e)[:100]}")
            sys.exit(1)

        # B. Mutate Exclusions
        client.command(exclusion_sql)
        for i in range(15):
            time.sleep(1)
            count = client.command("SELECT count() FROM system.mutations WHERE is_done = 0 AND table = 'mv_fact_task_vx'")
            if count == 0: break

        # C. Aggregate to Gold
        gold_sql = gold_template.replace('{start_date}', start_str).replace('{end_date}', end_str)
        try:
            client.command(gold_sql)
            print(f"   ► (Gold) L5 KPIs successfully aggregated and appended.")
        except Exception as e:
            print(f"   ❌ Gold Compute FAILED: {str(e)[:100]}")
            sys.exit(1)
            
    print("\n🎉 The entire Unified Pipe computed flawlessly!")

def main():
    parser = argparse.ArgumentParser(description="DMP Flowable Data Pipeline Execution Tool")
    parser.add_argument("--skip-existing", action="store_true", help="Automatically skip if table exists (safe mode)")
    parser.add_argument("--force", action="store_true", help="Automatically confirm all rebuilds (destructive)")
    parser.add_argument("--status", action="store_true", help="Display sync progress and row counts only")
    parser.add_argument("--backfill", action="store_true", help="Launch the Safe Unified Calculation Pipeline (Phase 3+4 chunks)")
    parser.add_argument("--daily", action="store_true", help="Daily incremental compute mode")
    parser.add_argument("--start", type=str, default="2025-10-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.date.today().strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    parser.add_argument("--step-days", type=int, default=10, help="Window size for bounded memory computing")
    parser.add_argument("--low-ram", action="store_true", help="Enable strict memory/timeout limits for Server 76 environments")
    
    args = parser.parse_args()
    
    print("="*60)
    print("DMP Flowable Execution Tool")
    print("="*60)
    
    try:
        client = get_client(is_low_ram=args.low_ram)
        client.query("SELECT 1")
    except Exception as e:
        print(f"ClickHouse connection failed: {e}")
        sys.exit(1)

    if args.status:
        show_status(client)
        return
        
    if args.daily:
        args.backfill = True
        args.start = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    if args.backfill:
        execute_unified_computation_pipeline(client, args)
        return

    # Ensure Databases exist first (only when normal DDL mode)
    initialize_databases(client)

    # Dynamic path resolution for sql directory
    script_dir = Path(__file__).resolve().parent
    sql_dir = script_dir.parent.parent / 'sql' / 'etl' / 'schema'
    
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
