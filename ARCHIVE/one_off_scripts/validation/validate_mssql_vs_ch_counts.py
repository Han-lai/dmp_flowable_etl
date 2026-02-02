#!/usr/bin/env python3
"""
MSSQL vs ClickHouse Bronze Layer Validation Script
==================================================
Purpose: Verify row counts and sample data consistency between MSSQL Source and ClickHouse Bronze Layer.
Usage: python scripts/validation/validate_mssql_vs_ch_counts.py [--env .env.validation]
"""

import os
import sys
import argparse
import time
import random
import logging
from typing import Dict, List, Optional, Tuple

# Try to import required libraries
try:
    import pyodbc
    import clickhouse_connect
except ImportError as e:
    print(f"❌ Missing required library: {e}")
    print("Please install: pip install pyodbc clickhouse-connect")
    sys.exit(1)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("DataValidator")

# Default Table Mapping (MSSQL -> ClickHouse)
TABLE_MAPPING = [
    # APP_SRV_BPM Schema
    {
        "mssql_schema": "APP_SRV_BPM.dbo",
        "mssql_table": "ACT_HI_PROCINST_0108",
        "ch_table": "bronze.bpm_act_hi_procinst",
        "pk": "ID_"
    },
    {
        "mssql_schema": "APP_SRV_BPM.dbo",
        "mssql_table": "ACT_HI_TASKINST_0108",
        "ch_table": "bronze.bpm_act_hi_taskinst",
        "pk": "ID_"
    },
    {
        "mssql_schema": "APP_SRV_BPM.dbo",
        "mssql_table": "ACT_HI_IDENTITYLINK_0108",
        "ch_table": "bronze.bpm_act_hi_identitylink",
        "pk": "ID_"
    },
    {
        "mssql_schema": "APP_SRV_BPM.dbo",
        "mssql_table": "ACT_HI_VARINST_0108",
        "ch_table": "bronze.bpm_act_hi_varinst",
        "pk": "ID_"
    },
    {
        "mssql_schema": "APP_SRV_BPM.dbo",
        "mssql_table": "ACT_RE_PROCDEF_0108",
        "ch_table": "bronze.bpm_act_re_procdef",
        "pk": "ID_"
    },
    # APP_SRV_COMMON Schema
    {
        "mssql_schema": "APP_SRV_COMMON.dbo",
        "mssql_table": "FlowableTaskStats",
        "ch_table": "bronze.common_flowable_task_stats", # Assumed name
        "pk": "TaskId" # inferred, might need adjustment
    },
    {
        "mssql_schema": "APP_SRV_COMMON.dbo",
        "mssql_table": "HR_Employee",
        "ch_table": "bronze.common_hr_employee",
        "pk": "EmployeeID" # inferred
    }
]

def load_env_file(filepath: str):
    """Simple .env loader to avoid python-dotenv dependency if possible, but useful for robustness"""
    if not os.path.exists(filepath):
        logger.warning(f"Config file not found: {filepath}")
        return

    logger.info(f"Loading config from {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

def get_mssql_conn():
    """Establish MSSQL Connection using pyodbc"""
    host = os.environ.get('MSSQL_HOST')
    port = os.environ.get('MSSQL_PORT', '1433')
    database = os.environ.get('MSSQL_DATABASE')
    user = os.environ.get('MSSQL_USER')
    password = os.environ.get('MSSQL_PASSWORD')
    driver = os.environ.get('MSSQL_DRIVER', 'ODBC Driver 17 for SQL Server')

    conn_str_list = [
        f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};",
        f"DRIVER={{SQL Server}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};"
    ]

    for conn_str in conn_str_list:
        try:
            logger.debug(f"Attempting MSSQL connection...")
            conn = pyodbc.connect(conn_str, timeout=10)
            return conn
        except Exception:
            continue
    
    raise ConnectionError("Failed to connect to MSSQL with available drivers.")

def get_clickhouse_client():
    """Establish ClickHouse Connection"""
    return clickhouse_connect.get_client(
        host=os.environ.get('CLICKHOUSE_HOST'),
        port=int(os.environ.get('CLICKHOUSE_PORT', 8123)),
        username=os.environ.get('CLICKHOUSE_USER', 'default'),
        password=os.environ.get('CLICKHOUSE_PASSWORD', ''),
        database=os.environ.get('CLICKHOUSE_DATABASE', 'default')
    )

def verify_table(mssql_conn, ch_client, table_info: dict, sample_size: int = 100):
    """Verify a single table: Count + Sample Check"""
    ms_full_name = f"{table_info['mssql_schema']}.{table_info['mssql_table']}"
    ch_full_name = table_info['ch_table']
    pk_col = table_info['pk']

    logger.info(f"Checking {ms_full_name} vs {ch_full_name}...")

    # 1. Row Count Comparison
    try:
        # MSSQL Count
        cursor = mssql_conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {ms_full_name}")
        ms_count = cursor.fetchone()[0]

        # ClickHouse Count
        ch_count = ch_client.command(f"SELECT count(*) FROM {ch_full_name}")

        diff = ms_count - ch_count
        diff_pct = (abs(diff) / ms_count * 100) if ms_count > 0 else 0.0
        
        status = "PASS" if diff == 0 else "FAIL" if diff_pct > 1.0 else "WARN" # Allow <1% stream lag
        
        print(f"   Counts: MSSQL={ms_count:,} | CH={ch_count:,} | Diff={diff:,} ({diff_pct:.4f}%) -> [{status}]")

    except Exception as e:
        logger.error(f"   Count check failed: {e}")
        return

    # 2. Sample Existence Check (Check if random MSSQL IDs exist in CH)
    if ms_count > 0:
        try:
            # Query random sample from MSSQL
            # Note: TABLESAMPLE or ORDER BY NEWID() can be slow on large tables, defaulting to TOP N for speed or simple rand
            sample_sql = f"SELECT TOP {sample_size} {pk_col} FROM {ms_full_name} ORDER BY {pk_col} DESC" # Check latest data mostly
            cursor.execute(sample_sql)
            rows = cursor.fetchall()
            
            if not rows:
                print("   Sample: No rows returned from MSSQL")
                return

            sample_ids = [str(r[0]) for r in rows]
            
            # Check existence in ClickHouse
            id_list_str = ",".join([f"'{x}'" for x in sample_ids])
            ch_check_sql = f"SELECT {pk_col} FROM {ch_full_name} WHERE {pk_col} IN ({id_list_str})"
            ch_result = ch_client.query(ch_check_sql)
            found_ids = set(row[0] for row in ch_result.result_rows)
            
            found_count = len(found_ids)
            missing = len(sample_ids) - found_count
            
            sample_status = "PASS" if missing == 0 else "FAIL"
            print(f"   Sample ({sample_size}): Found {found_count}, Missing {missing} -> [{sample_status}]")
            
            if missing > 0:
                print(f"   ⚠️ Warning: Some latest records from MSSQL are missing in CH. Might be sync lag.")

        except Exception as e:
            logger.error(f"   Sample check failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Validate MSSQL vs ClickHouse Data")
    parser.add_argument("--env", default=".env.validation", help="Path to env file")
    args = parser.parse_args()

    # Load Config
    load_env_file(args.env)

    # Connections
    try:
        logger.info("Connecting to MSSQL...")
        ms_conn = get_mssql_conn()
        
        logger.info("Connecting to ClickHouse...")
        ch_client = get_clickhouse_client()
        
        print("="*60)
        print(f"Validation Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        for table in TABLE_MAPPING:
            verify_table(ms_conn, ch_client, table)
            print("-" * 60)

    except KeyboardInterrupt:
        print("\nAborted by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        try:
            if 'ms_conn' in locals(): ms_conn.close()
            if 'ch_client' in locals(): ch_client.close()
        except:
            pass

if __name__ == "__main__":
    main()
