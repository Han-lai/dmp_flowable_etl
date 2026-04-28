#!/usr/bin/env python3
"""
DMP Flowable Data Pipeline Execution Tool (V4 - Activity Mode)
This is a dedicated wrapper for the V4 KPI refactor.
"""
import clickhouse_connect
import os
import sys
import argparse
import time
import datetime
from pathlib import Path
import pandas as pd
import yaml

# =================================================================
# 1. Configuration
# =================================================================

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'REDACTED_PASSWORD'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def load_pipeline_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # V4 SPECIFIC CONFIG
    config_path = os.path.join(base_dir, "config", "pipeline_config_v4.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading V4 pipeline configuration: {e}")
        sys.exit(1)

PIPELINE_CONFIG = load_pipeline_config()

def get_client(is_low_ram=False):
    config = CH_CONFIG.copy()
    if is_low_ram:
        config['send_receive_timeout'] = 300
    return clickhouse_connect.get_client(**config)

def get_table_metrics(client, table_name):
    try:
        sql = f"""
        SELECT 
            sum(rows) as row_count,
            sum(bytes_on_disk) as disk_size
        FROM system.parts 
        WHERE database = '{table_name.split('.')[0]}' 
          AND table = '{table_name.split('.')[1]}'
          AND active
        """
        res = client.query(sql)
        if res.result_rows:
            return res.result_rows[0][0], res.result_rows[0][1]
    except: pass
    return 0, 0

def get_checkpoint(client, phase, start, end):
    try:
        res = client.query(f"SELECT status FROM ops_metrics.etl_checkpoint FINAL WHERE phase = '{phase}' AND window_start = '{start}' AND window_end = '{end}'")
        if res.result_rows:
            return res.result_rows[0][0]
    except: pass
    return None

def update_checkpoint(client, phase, start, end, status, error="", duration_ms=0, rows=0, bytes=0):
    try:
        sql = f"""
        INSERT INTO ops_metrics.etl_checkpoint 
            (phase, window_start, window_end, status, error_msg, duration_ms, result_rows, result_bytes) 
        VALUES 
            ('{phase}', '{start}', '{end}', '{status}', '{error[:500]}', {duration_ms}, {rows}, {bytes})
        """
        client.command(sql)
    except: pass

def load_sql_template(template_name):
    script_dir = Path(__file__).resolve().parent
    template_path = script_dir.parent.parent / 'sql' / 'etl' / 'dml' / template_name
    return template_path.read_text(encoding='utf-8')

def show_status(client):
    print("\n" + "=" * 60)
    print("DMP V4 ACTIVITY PIPELINE STATUS")
    print("=" * 60)
    
    # Check V4 Tables
    print("\n[V4 Table Metrics]")
    v4_tables = [
        "gold.rmv_l5_milestone_v4_phys",
        "gold.rmv_l5_acc_v4_phys",
        "gold.rmv_l5_task_completion_v4_phys"
    ]
    for t in v4_tables:
        rows, size = get_table_metrics(client, t)
        print(f" - {t:40}: {rows:,} rows ({size:,} bytes)")

    # Recent Checkpoints
    try:
        cp_sql = "SELECT phase, window_start, window_end, status, update_time FROM ops_metrics.etl_checkpoint FINAL WHERE phase LIKE '%_v4' ORDER BY update_time DESC LIMIT 10"
        res = client.query(cp_sql)
        if res.result_rows:
            df = pd.DataFrame(res.result_rows, columns=['Phase', 'Start', 'End', 'Status', 'Updated At'])
            print("\n[Recent V4 Checkpoints]")
            print(df.to_string(index=False))
    except: pass

def execute_computation_pipeline(client, args):
    print("\n" + "="*80)
    print(f" [ V4 Computation Engine ] Activity Mode (Deltas)")
    print("="*80)
    
    if args.low_ram:
        client.command("SET max_threads = 1")
        client.command("SET max_memory_usage = 10000000000")

    if getattr(args, 'reset', False):
        print("\n[Safety] V4 Reset Initiated...")
        for t in PIPELINE_CONFIG.get('reset_targets', []):
            client.command(f"TRUNCATE TABLE IF EXISTS {t}")
        print("    V4 Tables cleared.")

    start_dtobj = datetime.datetime.strptime(args.start, "%Y-%m-%d")
    end_dtobj = datetime.datetime.strptime(args.end, "%Y-%m-%d") + datetime.timedelta(days=1, seconds=-1)
    
    windows = []
    curr = start_dtobj
    while curr <= end_dtobj:
        next_curr = curr + datetime.timedelta(days=args.step_days)
        if next_curr > end_dtobj + datetime.timedelta(seconds=1):
            next_curr = end_dtobj + datetime.timedelta(seconds=1)
        windows.append((curr, next_curr - datetime.timedelta(seconds=1)))
        curr = next_curr

    for stage in PIPELINE_CONFIG.get('pipeline_stages', []):
        print(f"\n[{stage['name']}]")
        for step in stage['steps']:
            phase_id = step['phase_id']
            sql_tpl = load_sql_template(step['template'])
            target_t = step.get('target_table')
            
            for (s_dt, e_dt) in windows:
                start_str = s_dt.strftime("%Y-%m-%d %H:%M:%S")
                end_str = e_dt.strftime("%Y-%m-%d %H:%M:%S")
                
                if get_checkpoint(client, phase_id, start_str, end_str) == 'SUCCESS' and not args.reset:
                    continue

                try:
                    print(f"   > Processing {phase_id}: {start_str} ~ {end_str} ...")
                    start_perf = time.perf_counter()
                    q = sql_tpl.replace('{start_date}', s_dt.strftime("%Y-%m-%d")) \
                               .replace('{end_date}', e_dt.strftime("%Y-%m-%d")) \
                               .replace('{start_ts}', start_str) \
                               .replace('{end_ts}', end_str)
                    client.command(q)
                    duration_ms = (time.perf_counter() - start_perf) * 1000
                    rows, bytes = get_table_metrics(client, target_t)
                    update_checkpoint(client, phase_id, start_str, end_str, 'SUCCESS', duration_ms=duration_ms, rows=rows, bytes=bytes)
                    print(f"     [Success] {duration_ms/1000:.2f}s")
                except Exception as e:
                    print(f"    CRITICAL FAILED at {start_str}: {e}")
                    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="DMP V4 Execution Tool")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default=datetime.date.today().strftime("%Y-%m-%d"))
    parser.add_argument("--step-days", type=int, default=10)
    parser.add_argument("--low-ram", action="store_true")
    
    args = parser.parse_args()
    client = get_client(is_low_ram=args.low_ram)
    
    if args.status:
        show_status(client)
    elif args.backfill:
        execute_computation_pipeline(client, args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
