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
import yaml

# =================================================================
# 1. Configuration
# =================================================================

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'localhost'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', '<CLICKHOUSE_PASSWORD>'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

# ==========================================
# Load Pipeline Configuration from YAML
# ==========================================
def load_pipeline_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config", "pipeline_config.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading pipeline configuration: {e}")
        sys.exit(1)

PIPELINE_CONFIG = load_pipeline_config()

# =================================================================
# 2. Core Functions
# =================================================================

def get_client(is_low_ram=False):
    """
    建立與 ClickHouse 資料庫的連線客體 (Client)。
    若為低記憶體模式 (is_low_ram=True)，則將連線逾時時間縮短為 300 秒，以防查詢卡死。
    """
    config = CH_CONFIG.copy()
    if is_low_ram:
        config['send_receive_timeout'] = 300
    return clickhouse_connect.get_client(**config)

def get_table_metrics(client, table_name):
    """Fetches row count and disk size for a given table."""
    try:
        # Query system.parts for the total size on disk and row count
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
    except Exception as e:
        print(f"    [Warn] Failed to fetch metrics for {table_name}: {e}")
    return 0, 0

def get_checkpoint(client, phase, start, end):
    """
    查詢特定 ETL 階段 (phase) 在指定時間窗格 (start~end) 是否已經執行成功。
    用以實現斷點續傳 (Checkpointing) 機制，避免重複運算。
    """
    try:
        res = client.query(f"SELECT status FROM ops_metrics.etl_checkpoint FINAL WHERE phase = '{phase}' AND window_start = '{start}' AND window_end = '{end}'")
        if res.result_rows:
            return res.result_rows[0][0]
    except Exception:
        pass
    return None

def update_checkpoint(client, phase, start, end, status, error="", duration_ms=0, rows=0, table_bytes=0):
    """
    更新 ETL 執行進度與狀態 (SUCCESS / FAILED) 至 ops_metrics.etl_checkpoint。
    此紀錄表使用 ReplacingMergeTree 引擎，相同的階段與時間窗格紀錄會自動覆蓋更新。
    """
    try:
        # Optimized for ReplacingMergeTree
        sql = f"""
        INSERT INTO ops_metrics.etl_checkpoint 
            (phase, window_start, window_end, status, error_msg, duration_ms, result_rows, result_bytes) 
        VALUES 
            ('{phase}', '{start}', '{end}', '{status}', '{error[:2000].replace("'", "''")}', {duration_ms}, {rows}, {table_bytes})
        """
        client.command(sql)
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
        wm_sql = "SELECT table_name, last_sync_time, min_data_time, max_data_time, sync_time, row_count FROM bronze._sync_watermark FINAL ORDER BY table_name"
        res = client.query(wm_sql)
        if res.result_rows:
            df = pd.DataFrame(res.result_rows, columns=['Table', 'Last Source TS', 'Min Data Time', 'Max Data Time', 'Sync At', 'Rows'])
            print("\n[Watermark Tracking (Data ingestion status & spans)]")
            print(df.to_string(index=False))
    except Exception as e:
        print(f"Error reading watermark status: {e}")

    # 2. ETL Checkpoints
    try:
        cp_sql = """
        SELECT 
            phase, window_start, window_end, status, 
            round(duration_ms/1000, 2) as duration_sec,
            formatReadableSize(result_bytes) as size,
            result_rows as rows,
            update_time
        FROM ops_metrics.etl_checkpoint FINAL 
        ORDER BY update_time DESC LIMIT 20
        """
        res = client.query(cp_sql)
        if res.result_rows:
            df = pd.DataFrame(res.result_rows, columns=['Phase', 'Start', 'End', 'Status', 'Dur(s)', 'Size', 'Rows', 'Updated At'])
            print("\n[ETL Checkpoints (Computation Progress & Metrics)]")
            print(df.to_string(index=False))
    except Exception as e:
        print(f"Error reading checkpoint status: {e}")

    # 3. Key Table Counts
    print("\n[Key Table Row Counts]")
    
    # Dynamically resolve target tables from config
    target_tables = ["bronze.bpm_act_hi_taskinst"] # Always include base table
    for stage in PIPELINE_CONFIG.get('pipeline_stages', []):
        for step in stage.get('steps', []):
            if step.get('target_table') and step['target_table'] not in target_tables:
                target_tables.append(step['target_table'])
    
    for t in target_tables:
        try:
            count = client.command(f"SELECT count() FROM {t}")
            print(f" - {t:35}: {count:,} rows")
        except Exception:
            print(f" - {t:35}: (Not created)")

def generate_windows(start_str, end_str, step_days):
    """
    依據起訖日期字串 (YYYY-MM-DD) 與步進天數，產生運算用的時間窗格列表。
    每個窗格為 (start_dt, end_dt) 的 datetime tuple，首尾相接（end 為下一窗 start 前一秒）；
    最後一個窗格若不足一個完整步進天數，會縮短為剩餘天數（remainder window）。
    """
    start_dtobj = datetime.datetime.strptime(start_str, "%Y-%m-%d")
    end_dtobj = datetime.datetime.strptime(end_str, "%Y-%m-%d") + datetime.timedelta(days=1, seconds=-1)

    windows = []
    curr = start_dtobj
    while curr <= end_dtobj:
        next_curr = curr + datetime.timedelta(days=step_days)
        if next_curr > end_dtobj + datetime.timedelta(seconds=1):
            next_curr = end_dtobj + datetime.timedelta(seconds=1)

        e = next_curr - datetime.timedelta(seconds=1)
        windows.append((curr, e))
        curr = next_curr

    return windows


def execute_computation_pipeline(client, args):
    """
    Core Engine: 執行安全的、基於時間窗格 (Time-Bounded) 的核心分析管線。
    主要特色：
    1. 記憶體最佳化設定 (Low-RAM mode spills to disk)
    2. 自動按天切分運算視窗 (Window Generation)
    3. 遇到 OOM 記憶體溢出時，自動將視窗切半並遞迴處理 (Auto-Split on OOM)
    """
    print("\n" + "="*80)
    print(f" [ Computation Engine ] Initiating Native Analytical Pipeline")
    print("="*80)
    
    if args.low_ram:
        # Core Memory Limits
        client.command("SET max_threads = 1")
        client.command("SET max_memory_usage = 10000000000") # 10GB hard cap (container: 11GB)

        # External Processing (Spill to Disk)
        client.command("SET max_bytes_before_external_group_by = 500000000") # 500MB force spill
        client.command("SET max_bytes_before_external_sort = 500000000")
        client.command("SET distributed_aggregation_memory_efficient = 1")
        client.command("SET aggregation_memory_efficient_merge_threads = 1")

        # Join Optimization
        client.command("SET max_bytes_in_join = 500000000")
        client.command("SET join_algorithm = 'grace_hash'")

        print(" Using Aggressive Mem-Optimized Settings (1 Thread, 10GB Limit, 500MB Spill)")



    # Safety: Reset Logic
    if getattr(args, 'reset', False):
        print("\n[Safety] Global Reset Initiated (--reset)...")
        for t in PIPELINE_CONFIG.get('reset_targets', []):
            client.command(f"TRUNCATE TABLE IF EXISTS {t}")
        client.command("TRUNCATE TABLE IF EXISTS ops_metrics.etl_checkpoint")
        print("    Tables and checkpoints cleared.")

    # Window Generation (Using datetime for finer granularity)
    windows = generate_windows(args.start, args.end, args.step_days)

    # Templates are loaded dynamically from pipeline_config.yaml (see loop below)

    def run_safe(phase_id, sql_tpl, start_dt, end_dt, target_table=None):
        """
        遞迴函數：安全執行單一時間窗格的 SQL 模板。
        - 具備防重跑機制 (Skip if SUCCESS)
        - 具備空窗格跳過機制 (Skip empty window)
        - 遇到記憶體不足 (OOM) 時，自動將時間窗格切半並遞迴執行
        """
        start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Skip if already successful
        if get_checkpoint(client, phase_id, start_str, end_str) == 'SUCCESS' and not args.reset:
            return

        # 2. Skip if the window is truly empty (Prevents Code: 41 and reduces ops)
        try:
            # We use taskinst as the primary indicator for windowed activity
            res = client.query(f"SELECT count() FROM bronze.bpm_act_hi_taskinst WHERE START_TIME_ >= '{start_str}' AND START_TIME_ <= '{end_str}'")
            if res.result_rows[0][0] == 0:
                # Skip for now, but don't mark as SUCCESS in checkpoint table
                # This allows future runs to process it if data is synced later
                return

        except Exception as check_e:

            print(f"    [Warn] Persistence check failed for {phase_id}: {check_e}")

        try:
            print(f"   > Processing {phase_id}: {start_str} ~ {end_str} ...")
            
            start_perf = time.perf_counter()
            
            # Replace both date and timestamp placeholders
            q = sql_tpl.replace('{start_date}', start_dt.strftime("%Y-%m-%d")) \
                       .replace('{end_date}', end_dt.strftime("%Y-%m-%d")) \
                       .replace('{start_ts}', start_str) \
                       .replace('{end_ts}', end_str)

            client.command(q)
            
            duration_ms = (time.perf_counter() - start_perf) * 1000
            
            # Capture table metrics
            rows, table_bytes = 0, 0
            if target_table:
                rows, table_bytes = get_table_metrics(client, target_table)
            
            update_checkpoint(client, phase_id, start_str, end_str, 'SUCCESS', 
                              duration_ms=duration_ms, rows=rows, table_bytes=table_bytes)
            
            print(f"     [Success] {duration_ms/1000:.2f}s | Rows: {rows:,} | Size: {table_bytes:,} bytes")
            time.sleep(0.5) # Breath for the server

        except Exception as e:

            err_msg = str(e)
            duration = end_dt - start_dt
            # Split if OOM and duration is more than 60 seconds (1 minute)
            if ("Memory limit exceeded" in err_msg or "Code: 241" in err_msg) and duration.total_seconds() > 60:
                mid_seconds = int(duration.total_seconds() // 2)
                mid_dt = start_dt + datetime.timedelta(seconds=mid_seconds)
                # Both halves share the midpoint boundary (closed interval on both sides).
                # Rows at exactly mid_dt are inserted by both halves; ReplacingMergeTree
                # deduplicates them on compaction. This avoids a 1-second data gap that
                # occurs when using mid-1s with sub-second (DateTime64) timestamps.
                print(f"   [OOM Alert] Memory Limit hit at {start_str} ~ {end_str}. Splitting window into halves...")
                run_safe(phase_id, sql_tpl, start_dt, mid_dt, target_table=target_table)
                run_safe(phase_id, sql_tpl, mid_dt, end_dt, target_table=target_table)
            else:


                update_checkpoint(client, phase_id, start_str, end_str, 'FAILED', err_msg)
                print(f"    CRITICAL FAILED at {start_str}: {err_msg}")
                sys.exit(1)

    # Loop through configured pipeline stages
    for stage in PIPELINE_CONFIG.get('pipeline_stages', []):
        stage_name = stage['name']
        print(f"\n[{stage_name}]")
        for step in stage['steps']:
            phase_id = step['phase_id']
            sql_tpl = load_sql_template(step['template'])
            target_t = step.get('target_table')
            
            for (s_dt, e_dt) in windows:
                # Add window header for readability if it's the first step in a multi-step stage
                if len(stage['steps']) > 1:
                    print(f"\n---- [Time Window: {s_dt.strftime('%Y-%m-%d %H:%M:%S')} ~ {e_dt.strftime('%Y-%m-%d %H:%M:%S')}] ----")
                run_safe(phase_id, sql_tpl, s_dt, e_dt, target_table=target_t)

    print("\n All calculation phases completed successfully!")

def main():
    """
    程式進入點與命令列參數解析 (CLI Parser)。
    支援四大模式：
    - --status: 儀表板模式 (檢查各表筆數與水位線)
    - --reset: 危險模式 (清空資料庫與 Checkpoint)
    - --daily: 自動接龍模式 (Auto-Catchup, 依據 Watermark 自動補齊落差)
    - --backfill: 手動回填模式 (依據 --start 與 --end 指定區間進行運算)
    """
    parser = argparse.ArgumentParser(description="DMP Flowable Execution Tool")
    parser.add_argument("--backfill", action="store_true", help="Launch the Safe Calculation Pipeline")
    parser.add_argument("--daily", action="store_true", help="Auto-process last 7 days")
    parser.add_argument("--status", action="store_true", help="Display progress and row counts")
    parser.add_argument("--reset", action="store_true", help="Truncate tables and clear checkpoints")
    parser.add_argument("--start", type=str, default="2025-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.date.today().strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    parser.add_argument("--step-days", type=int, default=10, help="Window size for memory safety")
    parser.add_argument("--low-ram", action="store_true", help="Enable 10GB RAM cap with disk spill (for 11GB containers)")
    
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

    # 2. Reset Mode
    if args.reset:
        try:
            client = get_client(is_low_ram=args.low_ram)
            print("Reset Mode: Truncating tables and clearing checkpoints...")
            for table in PIPELINE_CONFIG.get('reset_targets', []):
                print(f"  Truncating {table}...")
                client.command(f"TRUNCATE TABLE IF EXISTS {table}")
            print("  Clearing ETL checkpoints...")
            client.command("TRUNCATE TABLE IF EXISTS ops_metrics.etl_checkpoint")
            print("  Reset Completed.")
            if not args.backfill: return
        except Exception as e:
            print(f"Reset Error: {e}")
            sys.exit(1)

    # 3. Daily (Auto-Catchup) Mode Logic
    if args.daily:
        args.backfill = True
        print("\n[Auto-Catchup Mode Initiated]")
        try:
            client = get_client(is_low_ram=args.low_ram)
            
            # 3.1 Determine END: Read Data Watermark
            wm_res = client.query("SELECT maxOrNull(last_sync_time) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_taskinst'")
            if wm_res.result_rows and wm_res.result_rows[0][0]:
                watermark_dt = wm_res.result_rows[0][0]
                args.end = watermark_dt.strftime("%Y-%m-%d")
                print(f"  [End] Detected Source Data Watermark: {args.end}")
            else:
                args.end = datetime.date.today().strftime("%Y-%m-%d")
                print(f"  [End] No Watermark found. Using System Today: {args.end}")

            # 3.2 Determine START: min(bronze_max_data_time, last_etl_checkpoint) - 1 day
            # This prevents gaps when the checkpoint window ran ahead of actual bronze data.
            # We take the MIN across both taskinst and varinst because Silver JOINs both tables;
            # if varinst lags behind taskinst, using only taskinst would build Silver rows with
            # incomplete vx_type / mo_number data and never trigger a re-run.
            bronze_max_res = client.query(
                "SELECT minOrNull(max_data_time) FROM bronze._sync_watermark FINAL"
                " WHERE table_name IN ('bronze.bpm_act_hi_taskinst', 'bronze.bpm_act_hi_varinst')"
            )
            bronze_max_dt = None
            if bronze_max_res.result_rows and bronze_max_res.result_rows[0][0]:
                bronze_max_dt = bronze_max_res.result_rows[0][0]
                if isinstance(bronze_max_dt, str):
                    bronze_max_dt = datetime.datetime.strptime(bronze_max_dt, "%Y-%m-%d %H:%M:%S")
                print(f"  [Bronze Max] Min(taskinst, varinst) max_data_time: {bronze_max_dt.strftime('%Y-%m-%d')}")

            # Derive last phase_id from pipeline config to avoid hardcoding 'gold_summary'.
            last_phase_id = PIPELINE_CONFIG['pipeline_stages'][-1]['steps'][-1]['phase_id']
            cp_res = client.query(f"SELECT maxOrNull(window_end) FROM ops_metrics.etl_checkpoint FINAL WHERE status = 'SUCCESS' AND phase = '{last_phase_id}'")
            if cp_res.result_rows and cp_res.result_rows[0][0]:
                last_checkpoint_dt = cp_res.result_rows[0][0]
                if isinstance(last_checkpoint_dt, str):
                    last_checkpoint_dt = datetime.datetime.strptime(last_checkpoint_dt, "%Y-%m-%d %H:%M:%S")
                print(f"  [Checkpoint] Last {last_phase_id} checkpoint: {last_checkpoint_dt.strftime('%Y-%m-%d')}")

                # Use the earlier of the two to avoid skipping windows where bronze had no data yet
                if bronze_max_dt:
                    anchor_dt = min(last_checkpoint_dt, bronze_max_dt)
                    print(f"  [Start Anchor] min(checkpoint, bronze_max) = {anchor_dt.strftime('%Y-%m-%d')}")
                else:
                    anchor_dt = last_checkpoint_dt

                args.start = (anchor_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                print(f"  [Start] Overlapping 1 day before anchor: {args.start}")
            else:
                # Fallback if no checkpoint exists
                end_dtobj = datetime.datetime.strptime(args.end, "%Y-%m-%d")
                args.start = (end_dtobj - datetime.timedelta(days=14)).strftime("%Y-%m-%d")
                print(f"  [Start] No ETL Checkpoint found. Falling back to 14 days before watermark: {args.start}")

            print(f"  -> Automatically computing gap from {args.start} to {args.end}\n")
            
        except Exception as e:
            print(f"Warning: Auto-Catchup failed to detect boundaries ({e}). Falling back to static 7-day window.")
            args.start = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            args.end = datetime.date.today().strftime("%Y-%m-%d")

    # 4. Computation Mode
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
