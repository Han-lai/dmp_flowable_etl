#!/usr/bin/env python3
"""
Unified Sync Script for All Bronze Tables (Flowable + MDM + HR)
Syncs data from MSSQL to ClickHouse Bronze layer using JDBC Bridge.

Consolidates logic from:
- sync_batches_consolidated.py (Flowable Core)
- sync_bronze_missing_tables.py (Common/HR)
- New MDM Sync Logic

Features:
- Time-based batching for large tables (taskinst, varinst, procinst)
- Full sync for reference/master tables (MDM, HR, ProcDef)
- Retry mechanism
- Watermark tracking
"""

import sys
import logging
import time
import argparse
import os
from datetime import datetime, timedelta
import clickhouse_connect

# Load environment variables if needed (optional: can use python-dotenv if installed)
# For simplicity with built-in os.getenv, we assume variables are in the shell environment.

# ClickHouse Configuration (with defaults from old hardcoded values)
CLICKHOUSE_CONFIG = {
    "host": os.getenv("CLICKHOUSE_HOST", "REDACTED_IP"),
    "port": int(os.environ.get("CLICKHOUSE_PORT", "8121")),
    "username": os.getenv("CLICKHOUSE_USERNAME", "default"),
    "password": os.getenv("CLICKHOUSE_PASSWORD", "default"),
    "database": os.getenv("CLICKHOUSE_DATABASE", "default"),
    "send_receive_timeout": int(os.getenv("CLICKHOUSE_TIMEOUT", "600"))
}

# JDBC Bridge Configuration
JDBC_DATASOURCE_NAME = os.getenv("JDBC_DATASOURCE_NAME", "mssql_master")

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# (CLICKHOUSE_CONFIG and JDBC_DATASOURCE_NAME are now moved up and use os.getenv)

# ==========================================
# Table Configurations
# ==========================================
TABLE_CONFIGS = {
    # --- HR & Common (Small/Medium Tables - Full Sync) ---
    "hr_employee": {
        "source": "APP_SRV_COMMON.dbo.HR_Employee_0202",
        "target": "bronze.common_hr_employee",
        "strategy": "full",
        # Mapping: DeptCodeLname, UpdateTime -> ModifyDate, IsActive derived from TerminateDate
        "columns": "EmpCode, EmpName, DeptCode, DeptCodeLname, Email, (CASE WHEN TerminateDate IS NULL THEN 1 ELSE 0 END) AS IsActive, ModifyDate AS UpdateTime"
    },
    "emp_node_role": {
        "source": "APP_SRV_COMMON.dbo.EmpNodeRoleMapping_0202",
        "target": "bronze.common_emp_node_role_mapping",
        "strategy": "full",
        "columns": "EmpCode, NodeCode, UpdateTime, UpdateEmp"
    },
    "emp_org_info": {
        "source": "APP_SRV_COMMON.dbo.EmpOrgInfoMapping_0202",
        "target": "bronze.common_emp_org_info_mapping",
        "strategy": "full",
        "columns": "EmpCode, Plant, MFGFactoryId, UpdateTime, UpdateEmp"
    },
    "emp_user_group": {
        "source": "APP_SRV_COMMON.dbo.EmpUserGroupMapping_0202",
        "target": "bronze.common_emp_user_group_mapping",
        "strategy": "full",
        "columns": "EmpCode, UserGroupId, UpdateTime, UpdateEmp"
    },
    "user_group": {
        "source": "APP_SRV_COMMON.dbo.UserGroup_0202",
        "target": "bronze.common_user_group",
        "strategy": "full",
        "columns": "UserGroupId, UserGroupName, UserGroupDesc, UpdateTime, UpdateEmp"
    },
    "process_role_user": {
        "source": "APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202",
        "target": "bronze.common_process_role_user_mapping",
        "strategy": "full",
        "columns": "ID, RoleId, Plant, Factory, ProductionArea, LineName, EmpCode, Updater, UpdateDatetime, UpdateCount, Creator, CreateDatetime"
    },

    # --- MDM Masters (Small Tables - Full Sync) ---
    # Using User Provided Source Names
    "mdm_line_desc": {
        "source": "APP_SRV_COMMON.dbo.MDM_LINE_DESC_MASTER_0202",
        "target": "bronze.common_mdm_line_desc_master",
        "strategy": "full",
        "columns": "LINE_NAME, LINE_DESC, PROD_AREA_ID"
    },
    "mdm_prod_area": {
        "source": "APP_SRV_COMMON.dbo.MDM_PROD_AREA_MASTER_0202",
        "target": "bronze.common_mdm_prod_area_master",
        "strategy": "full",
        "columns": "PROD_AREA_ID, PROD_AREA_CODE, FACTORY, MFG_PLANT_ID"
    },
    "mdm_factory_area": {
        "source": "APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER_0202",
        "target": "bronze.common_mdm_factory_area_master",
        "strategy": "full",
        "columns": "FACTORY, FACTORY_DESC, PLANT_NODE, PLANT_NODE_DESC, REGION, MFG_SITE"
    },
    "mdm_mfg_site": {
        "source": "APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER_0202",
        "target": "bronze.common_mdm_mfg_site_master",
        "strategy": "full",
        "columns": "MFG_SITE, MFG_SITE_DESC"
    },
    "mdm_mfg_plant": {
        "source": "APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER_0202",
        "target": "bronze.common_mdm_mfg_plant_master",
        "strategy": "full",
        "columns": "MFG_PLANT_ID, MFG_PLANT_CODE, MFG_PLANT_DESC, FACTORY, VALIDITY"
    },
    # --- DMP Function Config (Full Sync) ---
    "dmp_func_config": {
        "source": "APP_SRV_COMMON.dbo.DMPFunctionConfig_0202",
        "target": "bronze.common_dmp_function_config",
        "strategy": "full",
        "columns": "*"
    },
    "dmp_func_client_mapping": {
        "source": "APP_SRV_COMMON.dbo.DMPFunctionClientMapping_0202",
        "target": "bronze.common_dmp_function_client_mapping",
        "strategy": "full",
        "columns": "*"
    },

    # --- Flowable Core (Small Tables - Full Sync) ---
    "procdef": {
        "source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0108",
        "target": "bronze.bpm_act_re_procdef",
        "strategy": "full",
        "columns": "*"
    },

    # --- Flowable Core (Large Tables - Batch Sync) ---
    # Priority: Syncing Large tables last to ensure Dimensions are ready
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
    },
    "procinst": {
        "source": "APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108",
        "target": "bronze.bpm_act_hi_procinst",
        "time_col": "START_TIME_",
        "strategy": "batch",
        "columns": "*"
    },
    "identitylink": {
        "source": "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK",
        "target": "bronze.bpm_act_hi_identitylink",
        "time_col": "CREATE_TIME_",
        "strategy": "batch",  # Can be large, safer to batch if time col exists
        "columns": "*"
    }
}

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
    """
    Creates the watermark tracking table if it doesn't exist.
    This table records the last successful sync time for each table
    to prevent fetching duplicate data in subsequent runs.
    """
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
    try:
        ts_val = last_sync_time_str
        if len(ts_val) == 10: 
            ts_val += " 00:00:00"
            
        sql = f"""
        INSERT INTO bronze._sync_watermark (table_name, last_sync_time, sync_time, row_count)
        VALUES ('{table_name}', toDateTime64('{ts_val}', 3), now64(3), {row_count})
        """
        client.command(sql)
        logger.info(f"  Watermark updated for {table_name}: {last_sync_time_str}")
    except Exception as e:
        logger.warning(f"  Failed to update watermark: {e}")

def get_last_watermark(client, table_name):
    """Fetches the last successful sync date for a given table."""
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
    """
    Queries the source MSSQL (via JDBC Bridge) to find the earliest record.
    Acts as a fail-safe start date.
    """
    source = config['source']
    time_col = config['time_col']
    
    logger.info(f"  Detecting earliest record for {source}...")
    
    # We use a subquery to get the min time via JDBC
    sql = f"""
    SELECT min({time_col}) 
    FROM jdbc('{JDBC_DATASOURCE_NAME}', 'SELECT min({time_col}) as {time_col} FROM {source}')
    """
    try:
        result = client.query(sql)
        if result.result_rows and result.result_rows[0][0]:
            dt = result.result_rows[0][0]
            # Handle if it is a datetime object or a string
            if hasattr(dt, 'strftime'):
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            return str(dt)
    except Exception as e:
        logger.warning(f"  Failed to detect min time from source: {e}")
    
    logger.info("  Detection failed, using ultimate fallback 2023-01-01")
    return "2023-01-01" # Ultimate fallback if detection fails

# =================================================================
# 4. Core Sync Logic
# =================================================================

def sync_batch(client, config, start_str, end_str):
    """
    Executes a single batch sync for a specific time range.
    Workflow: 1. Delete overlapping data in target -> 2. Insert new data from JDBC.
    """
    source = config['source']
    target = config['target']
    time_col = config['time_col']
    cols = config['columns']
    
    batch_id = f"{start_str}_{end_str}"
    
    logger.info(f"Processing Batch: {start_str} to {end_str}")
    
    # 1. Cleanup Target Range
    delete_sql = f"""
    ALTER TABLE {target} DELETE 
    WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}'
    """
    try:
        client.command(delete_sql)
    except Exception as e:
        logger.warning(f"  Cleanup warning: {e}")

    # 2. Insert Data
    insert_sql = f"""
    INSERT INTO {target}
    SELECT *, 
           '{batch_id}' as _batch_id,
           now64(3) as _extracted_at,
           1 as _sync_version
    FROM jdbc('{JDBC_DATASOURCE_NAME}', '
        SELECT {cols} FROM {source}
        WHERE {time_col} >= ''{start_str}'' 
          AND {time_col} < ''{end_str}''
    ')
    """
    
    max_retries = 3
    retry_delay = 30
    
    for attempt in range(max_retries):
        start_time = time.perf_counter()
        try:
            client.command(insert_sql)
            duration = time.perf_counter() - start_time
            
            # 3. Verify
            count_sql = f"""
            SELECT count() FROM {target} 
            WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}'
            """
            count = client.command(count_sql)
            logger.info(f"  Synced {count:,} rows in {duration:.2f}s")
            
            # 4. Update Watermark
            update_watermark(client, target, end_str, count)
            return count
            
        except Exception as e:
            logger.warning(f"  Batch failed (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logger.error(f"  All retries failed for batch {batch_id}")
                raise e

def sync_batch_adaptive(client, config, start_str, end_str):
    """
    Adaptive sync mode.
    If a large batch fails (usually due to MSSQL query timeout),
    this function will automatically split the range in half and retry.
    """
    try:
        return sync_batch(client, config, start_str, end_str)
    except Exception as e:
        logger.warning(f"Batch {start_str} to {end_str} failed. Checking if we can split...")
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        diff = end_dt - start_dt
        
        # Do not split if the interval is already less than 30 minutes
        if diff < timedelta(minutes=30):
            logger.error(f"  Range too small to split ({diff}). Aborting this block.")
            raise e
            
        # Split and recurse
        mid_dt = start_dt + (diff / 2)
        mid_str = mid_dt.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"  Splitting: {start_str} -> {mid_str} AND {mid_str} -> {end_str}")
        
        count1 = sync_batch_adaptive(client, config, start_str, mid_str)
        count2 = sync_batch_adaptive(client, config, mid_str, end_str)
        return count1 + count2

def sync_full(client, config):
    """
    Executes full sync logic.
    Truncates the target table first, then fetches all data from JDBC source at once.
    """
    source = config['source']
    target = config['target']
    cols = config['columns']
    
    logger.info(f"Full Syncing: {target}")
    
    # Truncate
    logger.info("  Truncating target table...")
    client.command(f"TRUNCATE TABLE {target}")
    
    # Insert
    # Check if target table has extra sync columns
    # We assume all Bronze tables created by our scripts have _batch_id, _extracted_at, _sync_version
    # If standard columns match perfectly with source+sync cols
    
    insert_sql = f"""
    INSERT INTO {target}
    SELECT *, 
           'full_sync_{datetime.now().strftime("%Y%m%d")}' as _batch_id,
           now64(3) as _extracted_at,
           1 as _sync_version
    FROM jdbc('{JDBC_DATASOURCE_NAME}', 'SELECT {cols} FROM {source}')
    """
    
    start_time = time.perf_counter()
    try:
        client.command(insert_sql)
        duration = time.perf_counter() - start_time
        count = client.command(f"SELECT count() FROM {target}")
        logger.info(f"  Synced {count:,} rows in {duration:.2f}s")
        update_watermark(client, target, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), count)
    except Exception as e:
        logger.error(f"  Full sync failed: {e}")

# =================================================================
# 5. Main Entry Point
# =================================================================

def main():
    parser = argparse.ArgumentParser(description="Unified Batch Sync for All Bronze Tables")
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
    
    for table_key in tables_to_sync:
        config = TABLE_CONFIGS[table_key]
        config['table_key'] = table_key 
        target_table = config['target']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting Sync for: {table_key.upper()}")
        logger.info(f"Source: {config['source']}")
        logger.info(f"Target: {target_table}")
        
        if config['strategy'] == 'full':
            if not args.dry_run:
                sync_full(client, config)
            else:
                logger.info("[DRY RUN] Would execute Full Sync (Truncate + Insert)")
        
        elif config['strategy'] == 'batch':
            # Watermark Logic
            start_date = args.start
            if not start_date:
                last_wm = get_last_watermark(client, target_table)
                if last_wm:
                    start_date = last_wm
                    logger.info(f"  Resuming from watermark: {start_date}")
                else:
                    start_date = get_source_min_time(client, config)
                    logger.info(f"  No watermark. Automatically detected start date from source: {start_date}")
            
            batches = generate_batches(start_date, args.end, args.step_days, args.step_hours)
            logger.info(f"Generated {len(batches)} batches from {start_date} to {args.end}")
            
            for i, (start, end) in enumerate(batches, 1):
                logger.info(f"Batch {i}/{len(batches)}: {start} -> {end}")
                if not args.dry_run:
                    try:
                        sync_batch_adaptive(client, config, start, end)
                    except Exception:
                        logger.error(f"Stopping sync for {table_key} due to error.")
                        break
                else:
                    logger.info("  [DRY RUN] Would execute batch sync")
                    
    logger.info("\nAll operations completed.")

if __name__ == "__main__":
    main()
