#!/usr/bin/env python3
"""
Consolidated Batch Sync Script for Flowable Tables
Syncs data from MSSQL (WJOAUATDB01S) to ClickHouse Bronze layer using JDBC Bridge.

Key Tables:
- ACT_HI_TASKINST_0108 (Batch)
- ACT_HI_VARINST_0108 (Batch)
- ACT_HI_PROCINST_0108 (Batch)
- ACT_RE_PROCDEF_0108 (Full)

Features:
- Time-based batching for large tables
- Retry mechanism
- Safe execution confirmation
"""

import sys
import logging
import time
import argparse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import clickhouse_connect

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ClickHouse Configuration
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 600
}

# Table Configurations
# Table Configurations (Ordered by approx size: Small -> Large)
TABLE_CONFIGS = {
    "procdef": {
        "source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0108",
        "target": "bronze.bpm_act_re_procdef",
        "strategy": "full",
        "columns": "*"
    },
    "procinst": {
        "source": "APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108",
        "target": "bronze.bpm_act_hi_procinst",
        "time_col": "START_TIME_",
        "strategy": "batch",
        "columns": "*"
    },
    "taskinst": {
        "source": "APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108",
        "target": "bronze.bpm_act_hi_taskinst",
        "time_col": "START_TIME_",
        "strategy": "batch",
        "columns": "*"
    },
    "varinst": {
        "source": "APP_SRV_BPM.dbo.ACT_HI_VARINST_0108",
        "target": "bronze.bpm_act_hi_varinst",
        "time_col": "CREATE_TIME_",
        "strategy": "batch",
        "columns": "*"
    }
}

def get_client():
    return clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)

def generate_batches(start_str, end_date_str, step_days=7, step_hours=0):
    """Generate time ranges for batch processing."""
    # support both date and datetime string
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        
    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        # Ensure we cover the full end day if only date is provided
        if len(end_date_str) == 10: 
            end_date = end_date + timedelta(days=1, microseconds=-1)
    
    current_date = start_date
    batches = []
    
    step_delta = timedelta(days=step_days)
    if step_hours > 0:
        step_delta = timedelta(hours=step_hours)
    
    while current_date < end_date:
        next_date = current_date + step_delta
        # Ensure we don't exceed end_date
        if next_date > end_date:
            next_date = end_date
            
        batches.append((current_date.strftime("%Y-%m-%d %H:%M:%S"), next_date.strftime("%Y-%m-%d %H:%M:%S")))
        current_date = next_date
        
    return batches

# ... (existing imports)

def setup_watermark_table(client):
    """Ensure watermark table exists."""
    sql = """
    CREATE TABLE IF NOT EXISTS bronze._sync_watermark (
        table_name String,
        last_sync_time DateTime64(3),
        sync_time DateTime64(3),
        row_count UInt64
    ) ENGINE = ReplacingMergeTree(sync_time)
    ORDER BY (table_name)
    """
    client.command(sql)

def update_watermark(client, table_name, last_sync_time_str, row_count):
    """Update watermark for a table."""
    try:
        # Convert date string to standard format if needed, simplistic string pass-through here
        # Assuming last_sync_time_str is YYYY-MM-DD, we can cast/store it widely.
        # But DateTime64 expects full timestamp. Let's ensure it's compatible.
        # If input is '2025-11-08', appending time ' 00:00:00' might be safer for ClickHouse DateTime64, 
        # or use toDateTime64('...', 3)
        
        # Safe format: '2025-11-08 00:00:00'
        ts_val = last_sync_time_str
        if len(ts_val) == 10: # YYYY-MM-DD
            ts_val += " 00:00:00"
            
        sql = f"""
        INSERT INTO bronze._sync_watermark (table_name, last_sync_time, sync_time, row_count)
        VALUES ('{table_name}', toDateTime64('{ts_val}', 3), now64(3), {row_count})
        """
        client.command(sql)
        logger.info(f"  💧 Watermark updated for {table_name}: {last_sync_time_str}")
    except Exception as e:
        logger.warning(f"  ⚠️ Failed to update watermark: {e}")

def sync_batch(client, config, start_str, end_str):
    """Sync a single batch for a table."""
    source = config['source']
    target = config['target']
    time_col = config['time_col']
    cols = config['columns']
    table_name = config['table_key'] # Need to pass this or derive
    
    batch_id = f"{start_str}_{end_str}"
    
    logger.info(f"Processing Batch: {start_str} to {end_str}")
    
    # ... (same cleanup logic) ...
    logger.info(f"  Cleaning target range...")
    delete_sql = f"""
    ALTER TABLE {target} DELETE 
    WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}'
    """
    try:
        client.command(delete_sql)
    except Exception as e:
        logger.warning(f"  Cleanup warning: {e}")

    # 2. Insert Data via JDBC
    insert_sql = f"""
    INSERT INTO {target}
    SELECT *, 
           '{batch_id}' as _batch_id,
           now64(3) as _extracted_at,
           1 as _sync_version
    FROM jdbc('mssql_master', '
        SELECT {cols} FROM {source}
        WHERE {time_col} >= ''{start_str}'' 
          AND {time_col} < ''{end_str}''
    ')
    """
    
    # Retry Mechanism for JDBC Instability
    max_retries = 5
    retry_delay = 60
    
    for attempt in range(max_retries):
        start_time = time.perf_counter()
        try:
            client.command(insert_sql)
            duration = time.perf_counter() - start_time
            
            # 3. Verify Count
            count_sql = f"""
            SELECT count() FROM {target} 
            WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}'
            """
            count = client.command(count_sql)
            logger.info(f"  ✅ Synced {count:,} rows in {duration:.2f}s")
            
            # 4. Update Watermark
            update_watermark(client, target, end_str, count)
            
            return count
            
        except Exception as e:
            logger.warning(f"  ⚠️ Batch failed (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"  Sleeping {retry_delay}s before retry...")
                time.sleep(retry_delay)
            else:
                logger.error(f"  ❌ All retries failed for batch {batch_id}")
                raise e

def sync_full(client, config):
    """Full sync for small tables."""
    source = config['source']
    target = config['target']
    cols = config['columns']
    
    logger.info(f"Full Syncing: {target}")
    
    # Truncate target
    logger.info("  Truncating target table...")
    client.command(f"TRUNCATE TABLE {target}")
    
    # Insert
    insert_sql = f"""
    INSERT INTO {target}
    SELECT *, 
           'full_sync' as _batch_id,
           now64(3) as _extracted_at,
           1 as _sync_version
    FROM jdbc('mssql_master', 'SELECT {cols} FROM {source}')
    """
    
    start_time = time.perf_counter()
    try:
        client.command(insert_sql)
        duration = time.perf_counter() - start_time
        count = client.command(f"SELECT count() FROM {target}")
        logger.info(f"  ✅ Synced {count:,} rows in {duration:.2f}s")
        
        # Update Watermark
        update_watermark(client, target, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), count)
        
    except Exception as e:
        logger.error(f"  ❌ Full sync failed: {e}")
        raise e

def get_last_watermark(client, table_name):
    """Get the last synced timestamp (watermark) for a table."""
    try:
        sql = f"SELECT max(last_sync_time) FROM bronze._sync_watermark WHERE table_name = '{table_name}'"
        result = client.query(sql)
        if result.result_rows and result.result_rows[0][0]:
            # ClickHouse returns datetime
            dt = result.result_rows[0][0]
            # Return full timestamp string
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.warning(f"Could not fetch watermark for {table_name}: {e}")
    return None

def sync_batch_adaptive(client, config, start_str, end_str):
    """Adaptive sync that splits time range on failure."""
    try:
        return sync_batch(client, config, start_str, end_str)
    except Exception as e:
        logger.warning(f"  ⚠️ Batch {start_str} to {end_str} failed. Checking if we can split...")
        
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        diff = end_dt - start_dt
        
        # Minimum threshold: 30 minutes
        if diff < timedelta(minutes=30):
            logger.error(f"  ❌ Range too small to split ({diff}). Aborting this block.")
            raise e
            
        # Split in half
        mid_dt = start_dt + (diff / 2)
        mid_str = mid_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(f"  🔄 Splitting batch into: {start_str} -> {mid_str} AND {mid_str} -> {end_str}")
        
        # Recursive calls
        count1 = sync_batch_adaptive(client, config, start_str, mid_str)
        count2 = sync_batch_adaptive(client, config, mid_str, end_str)
        return count1 + count2

def main():
    parser = argparse.ArgumentParser(description="Consolidated Batch Sync for Flowable Tables")
    parser.add_argument("--table", choices=list(TABLE_CONFIGS.keys()) + ['all'], default='all', help="Table to sync (auto-sorted if all)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD). If omitted, resumes from watermark or defaults to 2023-01-01.")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    parser.add_argument("--step-days", type=int, default=7, help="Batch size in days (default: 7)")
    parser.add_argument("--step-hours", type=int, default=0, help="Batch size in hours (overrides days if > 0)")
    parser.add_argument("--dry-run", action="store_true", help="Print batches without executing")
    
    args = parser.parse_args()
    
    client = get_client()
    setup_watermark_table(client) # Ensure table exists
    
    # If specific table selected, use that; otherwise use ordered list
    tables_to_sync = [args.table] if args.table != 'all' else list(TABLE_CONFIGS.keys())
    
    for table_key in tables_to_sync:
        config = TABLE_CONFIGS[table_key]
        config['table_key'] = table_key 
        target_table = config['target']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting Sync for: {table_key.upper()}")
        logger.info(f"Source: {config['source']}")
        
        # Determine start date logic
        start_date = args.start
        if not start_date and config['strategy'] == 'batch':
             last_wm = get_last_watermark(client, target_table)
             if last_wm:
                 start_date = last_wm
                 logger.info(f"  🌊 Resuming from watermark: {start_date}")
             else:
                 start_date = "2023-01-01"
                 logger.info(f"  🌊 No watermark found, starting from default: {start_date}")
        elif not start_date:
            start_date = "2023-01-01" # fallback
            
        logger.info(f"{'='*60}")
        
        if config['strategy'] == 'full':
            if not args.dry_run:
                try:
                    sync_full(client, config)
                except Exception as e:
                    logger.error(f"Failed to sync {table_key}, skipping to next table.")
            else:
                logger.info("[DRY RUN] Would execute Full Sync")
        
        elif config['strategy'] == 'batch':
            batches = generate_batches(start_date, args.end, args.step_days, args.step_hours)
            step_info = f"{args.step_hours} hours" if args.step_hours > 0 else f"{args.step_days} days"
            logger.info(f"Generated {len(batches)} batches from {start_date} to {args.end} (step: {step_info})")
            
            for i, (start, end) in enumerate(batches, 1):
                logger.info(f"Batch {i}/{len(batches)}: {start} -> {end}")
                if not args.dry_run:
                    try:
                        sync_batch_adaptive(client, config, start, end)
                    except Exception as e:
                        logger.error(f"Stopping sync for {table_key} due to error.")
                        break # Stop this table, proceed to next table
                else:
                    logger.info("  [DRY RUN] Would execute batch sync")
                    
    logger.info("\nAll operations completed.")

if __name__ == "__main__":
    main()
