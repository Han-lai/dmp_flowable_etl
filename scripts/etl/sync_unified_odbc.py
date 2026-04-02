#!/usr/bin/env python3
"""
Unified Sync Script for All Bronze Tables (Flowable + MDM + HR)
Syncs data from MSSQL to ClickHouse Bronze layer using native ODBC Table Engine.

Fully refactored to use `ENGINE = ODBC(...)` explicitly typed tables,
completely bypassing the MS-ODBC driver's unstable dynamic auto-discovery
that causes deadlocks on LOB (varchar(max)/xml) columns!
"""

import sys
import logging
import time
import argparse
import os
import yaml
from datetime import datetime, timedelta
import clickhouse_connect

# ClickHouse Configuration
CLICKHOUSE_CONFIG = {
    "host": os.getenv("CLICKHOUSE_HOST", "10.146.206.76"),
    "port": int(os.environ.get("CLICKHOUSE_PORT", "8123")),
    "username": os.getenv("CLICKHOUSE_USERNAME", "default"),
    "password": os.getenv("CLICKHOUSE_PASSWORD", "1qaz2wsx3edc"),
    "database": os.getenv("CLICKHOUSE_DATABASE", "default"),
    "send_receive_timeout": int(os.getenv("CLICKHOUSE_TIMEOUT", "3600")), # Increased to 1 hour
    "connect_timeout": 30,
}

# MSSQL ODBC Credentials
MSSQL_USER = os.getenv("MSSQL_USER", "APP_SRV_BPM")
MSSQL_PASSWORD = os.getenv("MSSQL_PASSWORD", "APP_SRV_BPM")
ODBC_DSN = os.getenv("ODBC_DSN", "MSSQL_DSN")

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ==========================================
# Helper: Parse source "DB.schema.table" -> dict
# ==========================================
def parse_source(source_str):
    """Parse 'APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108' into components."""
    parts = source_str.split(".")
    if len(parts) == 3:
        return {"db": parts[0], "schema": parts[1], "table": parts[2]}
    elif len(parts) == 2:
        return {"db": parts[0], "schema": "dbo", "table": parts[1]}
    else:
        return {"db": "APP_SRV_BPM", "schema": "dbo", "table": parts[0]}

def build_odbc_conn(db_name):
    """Build the ODBC connection string for a given database."""
    return f"DSN={ODBC_DSN};Database={db_name};Uid={MSSQL_USER};Pwd={MSSQL_PASSWORD};MARS_Connection=yes"


def load_configs():
    # 使用相對路徑尋找同目錄下 config/sync_tables.yaml
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config", "sync_tables.yaml")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"找不到設定檔：{config_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"讀取 YAML 發生錯誤：{e}")
        sys.exit(1)

TABLE_CONFIGS = load_configs()

def get_client():
    return clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)


def generate_batches(start_str, end_date_str, step_days=7, step_hours=0):
    """Generate time ranges for batch processing."""
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")

    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        if len(end_date_str) == 10:
            end_date = end_date + timedelta(days=1, microseconds=-1)

    current_date = start_date
    batches = []
    step_delta = timedelta(days=step_days)
    if step_hours > 0:
        step_delta = timedelta(hours=step_hours)

    while current_date < end_date:
        next_date = current_date + step_delta
        if next_date > end_date:
            next_date = end_date
        batches.append((current_date.strftime("%Y-%m-%d %H:%M:%S"), next_date.strftime("%Y-%m-%d %H:%M:%S")))
        current_date = next_date

    return batches


def setup_watermark_table(client):
    sql = """
    CREATE TABLE IF NOT EXISTS bronze._sync_watermark (
        table_name String,
        last_sync_time DateTime64(3),
        sync_time DateTime64(3),
        row_count UInt64,
        duration_ms Float64
    ) ENGINE = ReplacingMergeTree(sync_time)
    ORDER BY (table_name)
    """
    client.command(sql)


def update_watermark(client, table_name, last_sync_time_str, row_count, duration_ms=0):
    try:
        ts_val = last_sync_time_str
        if len(ts_val) == 10:
            ts_val += " 00:00:00"
        sql = f"""
        INSERT INTO bronze._sync_watermark (table_name, last_sync_time, sync_time, row_count, duration_ms)
        VALUES ('{table_name}', CAST('{ts_val}', 'DateTime64(3)'), now(), {row_count}, {duration_ms})
        """
        client.command(sql)
        logger.info(f"  Watermark updated for {table_name}: {last_sync_time_str}")
    except Exception as e:
        logger.warning(f"  Failed to update watermark: {e}")


def get_last_watermark(client, table_name):
    try:
        sql = f"SELECT maxOrNull(last_sync_time) FROM bronze._sync_watermark FINAL WHERE table_name = '{table_name}'"
        result = client.query(sql)
        if result.result_rows and result.result_rows[0][0]:
            dt = result.result_rows[0][0]
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.warning(f"Could not fetch watermark for {table_name}: {e}")
    return None


def get_source_min_time(client, config):
    logger.info("  [ODBC Safety] Skipping SELECT min() to prevent full table memory scan. Using default 2025-10-01")
    return "2025-10-01 00:00:00"


def sync_batch(client, config, start_str, end_str):
    target = config['target']
    time_col = config['time_col']
    cols = config.get('columns', '*')
    source_table_ref = config['source_table_ref']
    batch_id = f"{start_str}_{end_str}"
    
    QUERY_SETTINGS = "SETTINGS max_execution_time = 3600, odbc_bridge_use_connection_pooling = 1"

    logger.info(f"Processing Batch: {start_str} to {end_str}")

    select_clause = "*" if cols == '*' else cols

    insert_sql = f"""
    INSERT INTO {target}
    SELECT {select_clause},
           '{batch_id}' as _batch_id,
           now() as _extracted_at,
           1 as _sync_version
    FROM {source_table_ref}
    WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}'
    {QUERY_SETTINGS}
    """

    max_retries = 3
    retry_delay = 30
    current_client = client

    for attempt in range(max_retries):
        start_time = time.perf_counter()
        try:
            current_client.command(insert_sql)
            duration = time.perf_counter() - start_time
            duration_ms = duration * 1000
            count_sql = f"SELECT count() FROM {target} WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}' {QUERY_SETTINGS}"
            count = current_client.command(count_sql)
            logger.info(f"  Synced {count:,} rows in {duration:.2f}s")
            return count, duration_ms
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"  Batch failed (Attempt {attempt + 1}/{max_retries}): {err_msg}")
            
            if "Code: 1000" in err_msg or "Timeout" in err_msg or "Code: 241" in err_msg or "MEMORY_LIMIT" in err_msg:
                logger.warning("  Timeout or OOM detected. Aborting retries to trigger adaptive range splitting.")
                raise e
                
            if attempt < max_retries - 1:
                logger.info("  Refreshing client session to avoid session locks...")
                try: current_client.close()
                except: pass
                current_client = get_client() 
                time.sleep(retry_delay)
            else:
                logger.error(f"  All retries failed for batch {batch_id}")
                raise e


def sync_batch_adaptive(client, config, start_str, end_str):
    try:
        return sync_batch(client, config, start_str, end_str)
    except Exception as e:
        logger.warning(f"Batch {start_str} to {end_str} failed. Checking if we can split...")
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        diff = end_dt - start_dt

        if diff < timedelta(minutes=30):
            logger.error(f"  Range too small to split ({diff}). Aborting this block.")
            raise e

        mid_dt = start_dt + (diff / 2)
        mid_str = mid_dt.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"  Splitting: {start_str} -> {mid_str} AND {mid_str} -> {end_str}")

        count1, dur1 = sync_batch_adaptive(client, config, start_str, mid_str)
        count2, dur2 = sync_batch_adaptive(client, config, mid_str, end_str)
        return count1 + count2, dur1 + dur2


def sync_full(client, config):
    target = config['target']
    cols = config.get('columns', '*')
    source_table_ref = config['source_table_ref']
    range_col = config.get('range_col')
    range_batches = config.get('range_batches')

    logger.info(f"Full Syncing: {target}")
    select_clause = "*" if cols == '*' else cols
    QUERY_SETTINGS = "SETTINGS max_execution_time = 3600, odbc_bridge_use_connection_pooling = 1"

    if range_batches and range_col:
        logger.info(f"  [Range Batch] Using {range_col} ranges ({len(range_batches)} batches) to avoid ODBC buffer overflow")
        total_count = 0
        total_duration = 0  # 累計總時間
        for i, (range_start, range_end) in enumerate(range_batches, 1):
            batch_id = f"full_sync_{datetime.now().strftime('%Y%m%d')}_{i}"
            insert_sql = f"""
            INSERT INTO {target}
            SELECT {select_clause},
                   '{batch_id}' as _batch_id,
                   now() as _extracted_at,
                   1 as _sync_version
            FROM {source_table_ref}
            WHERE {range_col} >= '{range_start}' AND {range_col} < '{range_end}'
            {QUERY_SETTINGS}
            """
            start_time = time.perf_counter()
            try:
                client.command(insert_sql)
                duration = (time.perf_counter() - start_time) * 1000
                total_duration += duration  # 累加時間
                count = client.command(f"SELECT count() FROM {target} WHERE {range_col} >= '{range_start}' AND {range_col} < '{range_end}' {QUERY_SETTINGS}")
                total_count += count
                logger.info(f"  Batch {i}/{len(range_batches)} [{range_start}-{range_end}]: {count:,} rows in {duration/1000:.2f}s")
            except Exception as e:
                logger.error(f"  Batch {i} [{range_start}-{range_end}] failed: {e}")
        logger.info(f"  Total synced: {total_count:,} rows in {total_duration/1000:.2f}s")
        update_watermark(client, target, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_count, total_duration)
        return total_count
    else:
        start_t = time.time()
        insert_sql = f"""
        INSERT INTO {target}
        SELECT {select_clause},
               'full_sync_{datetime.now().strftime("%Y%m%d")}' as _batch_id,
               now() as _extracted_at,
               1 as _sync_version
        FROM {source_table_ref}
        {QUERY_SETTINGS}
        """
        try:
            client.command(insert_sql)
            duration = (time.time() - start_t) * 1000
            count = client.command(f"SELECT count() FROM {target}")
            logger.info(f"  Synced {count:,} rows in {duration/1000:.2f}s")
            update_watermark(client, target, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), count, duration)
        except Exception as e:
            logger.error(f"  Full sync failed: {e}")
            raise e
        return count


def main():
    parser = argparse.ArgumentParser(description="Unified ODBC Sync using Explicit Table Engines")
    parser.add_argument("--table", choices=list(TABLE_CONFIGS.keys()) + ['all'], default='all', help="Table to sync")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    parser.add_argument("--step-days", type=int, default=7, help="Batch size in days")
    parser.add_argument("--step-hours", type=int, default=0, help="Batch size in hours")
    parser.add_argument("--dry-run", action="store_true", help="Print batches without executing")

    args = parser.parse_args()

    client = get_client()
    setup_watermark_table(client)

    tables_to_sync = [args.table] if args.table != 'all' else list(TABLE_CONFIGS.keys())
    logger.info(f"Target Tables: {', '.join(tables_to_sync)}")

    stats = []

    for table_key in tables_to_sync:
        start_t = time.time()
        status = "SUCCESS"
        row_count = 0
        config = TABLE_CONFIGS[table_key]
        config['table_key'] = table_key
        target_table = config['target']
        src = parse_source(config['source'])
        conn_str = build_odbc_conn(src['db'])

        logger.info(f"\n{'='*60}")
        logger.info(f"Starting Sync for: {table_key.upper()}")

        # Ensure pure explicit ODBC table proxy creation!
        temp_name = f"odbc_temp_{table_key}"
        engine_ddl = config.get('engine_ddl')
        
        if not engine_ddl:
            logger.error(f"Missing engine_ddl for {table_key}. All tables MUST use explicit ddl schemas! Aborting.")
            continue

        if not args.dry_run:
            client.command(f"DROP TABLE IF EXISTS {temp_name}")
            create_sql = f"""
            CREATE TABLE {temp_name} (
                {engine_ddl}
            ) ENGINE = ODBC('{conn_str}', '{src['schema']}', '{src['table']}')
            """
            client.command(create_sql)
            config['source_table_ref'] = temp_name
            logger.info(f"  [DDL Bypass] Created explicit Safe Table Engine: {temp_name}")
        else:
            config['source_table_ref'] = temp_name

        try:
            if config['strategy'] == 'full':
                if not args.dry_run:
                    row_count = sync_full(client, config)
                else:
                    logger.info("  [DRY RUN] Would execute Full Sync via Temp Engine")

            elif config['strategy'] == 'batch':
                start_date = args.start
                if not start_date:
                    last_wm = get_last_watermark(client, target_table)
                    if last_wm:
                        start_date = last_wm
                        logger.info(f"  Resuming from watermark: {start_date}")
                    else:
                        start_date = get_source_min_time(client, config)
                        logger.info(f"  No watermark. Auto-detected start: {start_date}")

                effective_step_days = config.get('step_days', args.step_days)
                effective_step_hours = config.get('step_hours', args.step_hours)
                batches = generate_batches(start_date, args.end, effective_step_days, effective_step_hours)
                logger.info(f"Generated {len(batches)} batches from {start_date} to {args.end}")

                session_total = 0
                session_total_duration = 0  # 累計總時間
                for i, (start, end) in enumerate(batches, 1):
                    logger.info(f"Batch {i}/{len(batches)}: {start} -> {end}")
                    if not args.dry_run:
                        batch_count, batch_duration = sync_batch_adaptive(client, config, start, end)
                        session_total += batch_count
                        session_total_duration += batch_duration  # 累加時間
                        row_count = session_total
                        update_watermark(client, target_table, end, session_total, session_total_duration)
                    else:
                        logger.info("  [DRY RUN] Would execute batch sync via Temp Engine")

        except Exception as e:
            logger.error(f"Stopping sync for {table_key} due to error: {e}")
            status = f"FAILED: {str(e)[:50]}"
        finally:
            duration = time.time() - start_t
            stats.append({
                "table": table_key,
                "duration": duration,
                "rows": row_count,
                "status": status
            })
            if not args.dry_run:
                client.command(f"DROP TABLE IF EXISTS {temp_name}")

    # Final Summary Report
    logger.info(f"\n{'='*60}")
    logger.info("FINAL SYNC SUMMARY")
    logger.info(f"{'Table':<35} | {'Duration':<10} | {'Rows':<10} | {'Status'}")
    logger.info("-" * 80)
    for s in stats:
        dur_str = f"{s['duration']:.2f}s"
        row_str = f"{s['rows']:,}"
        logger.info(f"{s['table']:<35} | {dur_str:>10} | {row_str:>10} | {s['status']}")
    logger.info("-" * 80)
    logger.info("All operations completed.")

if __name__ == "__main__":
    main()
