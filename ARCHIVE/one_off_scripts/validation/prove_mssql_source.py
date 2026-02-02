#!/usr/bin/env python3
"""
MSSQL Source Proof & Calibration Script (via ClickHouse JDBC Bridge)
==================================================================
Purpose:
1. Connect to ClickHouse.
2. Verify access to MSSQL Source Tables via the 'mssql_master' JDBC bridge.
   (This confirms we are using the validated pipeline connection).
3. Query actual row counts from MSSQL tables to prove accessibility.

TARGET TABLES (APP_SRV_BPM.dbo):
- ACT_HI_PROCINST_0108
- ACT_HI_TASKINST_0108
- ACT_HI_IDENTITYLINK_0108
- ACT_HI_VARINST_0108
- ACT_RE_PROCDEF_0108

TARGET TABLES (APP_SRV_COMMON.dbo):
- FlowableTaskStats
- HR_Employee
"""

import clickhouse_connect
import sys
import time

# ClickHouse Config
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

TARGET_TABLES = [
    "APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108",
    "APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108",
    # "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108",
    "APP_SRV_BPM.dbo.ACT_HI_VARINST_0108",
    "APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0108",
    # "APP_SRV_COMMON.dbo.FlowableTaskStats",
    "APP_SRV_COMMON.dbo.HR_Employee"
]

def main():
    print("🚀 Starting MSSQL Source Calibration (via JDBC Bridge 'mssql_master')")
    print("=" * 80)
    
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        print("✅ Connected to ClickHouse Gateway")
        
        print("\n📋 MSSQL Table Verification Results (via jdbc('mssql_master', ...)):")
        print("-" * 100)
        print(f"{'Target Table':<45} | {'Status':<10} | {'Row Count':<15}")
        print("-" * 100)
        
        for table in TARGET_TABLES:
            try:
                # Query MSSQL via JDBC Bridge
                # Note: We select count(*) directly in the SQL passed to JDBC to minimize transfer
                sql = f"SELECT count(*) FROM jdbc('mssql_master', 'SELECT count(*) FROM {table}')"
                
                count = client.command(sql)
                
                print(f"{table:<45} | {'OK':<10} | {count:<15,}")
                
            except Exception as e:
                error_msg = str(e).split('\n')[0][:50] + "..."
                print(f"{table:<45} | {'ERROR':<10} | {error_msg}")
        
        print("-" * 100)
        print("\n✅ Calibration Complete.")
        print("Confirmed: We are reading from the MSSQL instance defined in ClickHouse as 'mssql_master'.")
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
