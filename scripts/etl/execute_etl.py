#!/usr/bin/env python3
"""
DMP Flowable Data Pipeline Execution Tool
Purpose: Focused, window-based data transformation (Bronze -> Silver -> Gold).
Provides: Backfill, Daily, Reset, and Status monitoring.
"""
import clickhouse_connect
import os
import sys
import argparse
import time
import datetime
from pathlib import Path
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

# =================================================================
# 2. Core Functions
# =================================================================

def get_client(is_low_ram=False):
    config = CH_CONFIG.copy()
    if is_low_ram:
        config['send_receive_timeout'] = 300
    return clickhouse_connect.get_client(**config)

def get_checkpoint(client, phase, start, end):
    try:
        res = client.query(f"SELECT status FROM bronze.etl_checkpoint FINAL WHERE phase = '{phase}' AND window_start = '{start}' AND window_end = '{end}'")
        if res.result_rows:
            return res.result_rows[0][0]
    except: pass
    return None

def update_checkpoint(client, phase, start, end, status, error=""):
    try:
        client.command(f"INSERT INTO bronze.etl_checkpoint (phase, window_start, window_end, status, error_msg) VALUES ('{phase}', '{start}', '{end}', '{status}', '{error[:500]}')")
    except Exception as e:
        print(f"Warning: Failed to update checkpoint: {e}")

def load_sql_template(template_name):
    script_dir = Path(__file__).resolve().parent
    template_path = script_dir.parent.parent / 'sql' / 'etl' / 'dml' / template_name
    return template_path.read_text(encoding='utf-8')

def show_status(client):
    """Displays sync progress, row counts, and checkpoints."""
    print("\n" + "=" * 60)
    print("DMP Pipeline Status Dashboard")
    print("=" * 60)
    
    # 1. Watermark Tracking
    try:
        wm_sql = "SELECT table_name, last_sync_time, sync_time, row_count FROM bronze._sync_watermark FINAL ORDER BY table_name"
        res = client.query(wm_sql)
        if res.result_rows:
            df = pd.DataFrame(res.result_rows, columns=['Table', 'Last Source TS', 'Sync At', 'Rows'])
            print("\n[Watermark Tracking]")
            print(df.to_string(index=False))
    except: pass

    # 2. ETL Checkpoints
    try:
        cp_sql = "SELECT phase, window_start, window_end, status, update_time FROM bronze.etl_checkpoint FINAL ORDER BY phase, window_start"
        res = client.query(cp_sql)
        if res.result_rows:
            df = pd.DataFrame(res.result_rows, columns=['Phase', 'Start', 'End', 'Status', 'Updated At'])
            print("\n[ETL Checkpoints (Computation Progress)]")
            print(df.to_string(index=False))
    except: pass

    # 3. Key Table Counts
    print("\n[Key Table Row Counts]")
    for t in ["bronze.bpm_act_hi_taskinst", "silver.mv_varinst_pivoted", "silver.mv_fact_task_vx", "gold.rmv_l5_task_completion_phys"]:
        try:
            count = client.command(f"SELECT count() FROM {t}")
            print(f" - {t:35}: {count:,} rows")
        except:
            print(f" - {t:35}: (Not created)")

def execute_computation_pipeline(client, args):
    """Core Engine for Safe Low-RAM Time-Bounded Computing."""
    print("\n" + "="*80)
    print(f" [ Computation Engine ] Initiating Native Analytical Pipeline")
    print("="*80)
    
    if args.low_ram:
        client.command("SET max_threads = 1")
        client.command("SET max_memory_usage = 6000000000")
        client.command("SET max_bytes_before_external_group_by = 3000000000")
        client.command("SET join_algorithm = 'auto'")
        print(" Using Mem-Optimized Settings (1 Thread, 6GB Limit)")

    # Safety: Reset Logic
    if getattr(args, 'reset', False):
        print("\n[Safety] Global Reset Initiated (--reset)...")
        for t in ["silver.mv_varinst_pivoted", "silver.mv_fact_task_vx", "gold.rmv_l5_task_completion_phys"]:
            client.command(f"TRUNCATE TABLE IF EXISTS {t}")
        client.command("TRUNCATE TABLE IF EXISTS bronze.etl_checkpoint")
        print("    Tables and checkpoints cleared.")

    # Window Generation
    start_dateobj = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
    end_dateobj = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    
    windows = []
    curr = start_dateobj
    while curr <= end_dateobj:
        next_curr = curr + datetime.timedelta(days=args.step_days)
        e = next_curr - datetime.timedelta(days=1)
        windows.append((curr.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")))
        curr = next_curr

    # Load Templates
    pivot_template = load_sql_template('backfill_pivot.sql')
    silver_tpl = load_sql_template('backfill_silver.sql')
    exclusion_sql = load_sql_template('backfill_exclusion.sql')
    gold_tpl = load_sql_template('backfill_gold.sql')

    def run_safe(phase_name, sql_tpl, start_dt, end_dt):
        """Recursive function to process windows with auto-split on OOM."""
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        
        if get_checkpoint(client, phase_name, start_str, end_str) == 'SUCCESS' and not args.reset:
            return

        try:
            print(f"   > Processing {phase_name}: {start_str} ~ {end_str} ...")
            
            # Special case for exclusions which doesn't use dates
            if sql_tpl == exclusion_sql:
                client.command(sql_tpl)
            else:
                client.command(sql_tpl.replace('{start_date}', start_str).replace('{end_date}', end_str))
            
            # Additional wait for mutations if needed
            if phase_name == 'silver_exclusions':
                for _ in range(15):
                    time.sleep(1)
                    if client.command("SELECT count() FROM system.mutations WHERE is_done = 0 AND table = 'mv_fact_task_vx'") == 0: break
            
            update_checkpoint(client, phase_name, start_str, end_str, 'SUCCESS')
        except Exception as e:
            err_msg = str(e)
            # Check for memory limit exceeded (ClickHouse Code 241 or similar keywords)
            if ("Memory limit exceeded" in err_msg or "Code: 241" in err_msg) and (end_dt - start_dt).days >= 1:
                mid_days = (end_dt - start_dt).days // 2
                mid_dt = start_dt + datetime.timedelta(days=mid_days)
                print(f"   [OOM Alert] Memory Limit hit at {start_str} ~ {end_str}. Splitting window into halves...")
                run_safe(phase_name, sql_tpl, start_dt, mid_dt)
                run_safe(phase_name, sql_tpl, mid_dt + datetime.timedelta(days=1), end_dt)
            else:
                update_checkpoint(client, phase_name, start_str, end_str, 'FAILED', err_msg)
                print(f"    CRITICAL FAILED at {start_str}: {err_msg}")
                sys.exit(1)

    # Loop 1: Dimension Pivot
    print("\n[Stage 1/2] Computing silver_varinst_pivoted (Self-Adaptive)")
    for (s_str, e_str) in windows:
        s_dt = datetime.datetime.strptime(s_str, "%Y-%m-%d").date()
        e_dt = datetime.datetime.strptime(e_str, "%Y-%m-%d").date()
        run_safe('silver_varinst_pivoted', pivot_template, s_dt, e_dt)

    # Loop 2: Fact & Gold Aggregation
    print("\n[Stage 2/2] Computing gold_task_completion (Self-Adaptive)")
    for (s_str, e_str) in windows:
        s_dt = datetime.datetime.strptime(s_str, "%Y-%m-%d").date()
        e_dt = datetime.datetime.strptime(e_str, "%Y-%m-%d").date()
        
        print(f"\n---- [Time Window: {s_str} ~ {e_str}] ----")
        run_safe('silver_facts', silver_tpl, s_dt, e_dt)
        run_safe('silver_exclusions', exclusion_sql, s_dt, e_dt)
        run_safe('gold_task_completion', gold_tpl, s_dt, e_dt)

    print("\n All calculation phases completed successfully!")

def main():
    parser = argparse.ArgumentParser(description="DMP Flowable Execution Tool")
    parser.add_argument("--backfill", action="store_true", help="Launch the Safe Calculation Pipeline")
    parser.add_argument("--daily", action="store_true", help="Auto-process last 7 days")
    parser.add_argument("--status", action="store_true", help="Display progress and row counts")
    parser.add_argument("--reset", action="store_true", help="Truncate tables and clear checkpoints")
    parser.add_argument("--start", type=str, default="2025-10-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.date.today().strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    parser.add_argument("--step-days", type=int, default=10, help="Window size for memory safety")
    parser.add_argument("--low-ram", action="store_true", help="Enable 6GB RAM optimization")
    
    args = parser.parse_args()
    
    # 1. Dashboard Mode
    if args.status:
        try:
            client = get_client(is_low_ram=args.low_ram)
            show_status(client)
            return
        except Exception as e:
            print(f"Error reading status: {e}")
            sys.exit(1)

    # 2. Daily Mode Logic
    if args.daily:
        args.backfill = True
        args.start = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"Daily Mode: Focus on last 7 days from {args.start}")

    # 3. Computation Mode
    if args.backfill:
        try:
            client = get_client(is_low_ram=args.low_ram)
            execute_computation_pipeline(client, args)
        except Exception as e:
            print(f"Execution Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
