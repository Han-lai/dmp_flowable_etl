#!/usr/bin/env python3
"""
MSSQL vs ClickHouse Data Consistency Check
==========================================
Uses 'jdbc(\'mssql_master\', ...)' to query MSSQL counts securely.
Compares with ClickHouse Bronze table counts.

Target Tables:
1. ACT_HI_PROCINST_0108
2. ACT_HI_TASKINST_0108
3. ACT_HI_IDENTITYLINK_0108
4. ACT_HI_VARINST_0108
5. ACT_RE_PROCDEF_0108
6. FlowableTaskStats
7. HR_Employee
"""

import clickhouse_connect
import sys
import time

# ClickHouse Config
CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# Table Mapping: (MSSQL Table Path, ClickHouse Bronze Table)
TABLE_PAIRS = [
    ("APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108", "bronze.bpm_act_hi_procinst"),
    ("APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108", "bronze.bpm_act_hi_taskinst"),
    ("APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108", "bronze.bpm_act_hi_identitylink"),
    ("APP_SRV_BPM.dbo.ACT_HI_VARINST_0108", "bronze.bpm_act_hi_varinst"),
    ("APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0108", "bronze.bpm_act_re_procdef"),
    ("APP_SRV_COMMON.dbo.FlowableTaskStats", "bronze.common_flowable_task_stats"),
    ("APP_SRV_COMMON.dbo.HR_Employee", "bronze.common_hr_employee")
]

def main():
    print("🚀 Starting Data Consistency Check (MSSQL via JDBC Bridge <-> ClickHouse Bronze)")
    print("=" * 100)
    print(f"{'Table Name':<40} | {'MSSQL Count':<15} | {'CH Count':<15} | {'Diff':<10} | {'Status':<10}")
    print("-" * 100)
    
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        all_match = True
        
        for ms_table, ch_table in TABLE_PAIRS:
            short_name = ms_table.split('.')[-1]
            sys.stdout.write(f"⏳ Checking {short_name}...")
            sys.stdout.flush()
            
            # 1. Query MSSQL Count (via JDBC)
            try:
                ms_sql = f"SELECT count(*) FROM jdbc('mssql_master', 'SELECT count(*) FROM {ms_table}')"
                ms_count = client.command(ms_sql)
            except Exception as e:
                print(f"\n❌ Error querying MSSQL {short_name}: {e}")
                ms_count = -1
            
            # 2. Query ClickHouse Count
            try:
                ch_count = client.command(f"SELECT count(*) FROM {ch_table}")
            except Exception as e:
                print(f"\n❌ Error querying ClickHouse {ch_table}: {e}")
                ch_count = -1
                
            # 3. Compare
            sys.stdout.write("\r") # Overwrite "Checking..."
            
            if ms_count >= 0 and ch_count >= 0:
                diff = ms_count - ch_count
                status = "✅ MATCH" if diff == 0 else "⚠️ DIFF"
                print(f"{short_name:<40} | {ms_count:<15,} | {ch_count:<15,} | {diff:<10} | {status:<10}")
                
                if diff != 0:
                    all_match = False
            else:
                print(f"{short_name:<40} | {'ERROR':<15} | {'ERROR':<15} | {'-':<10} | {'❌ FAIL':<10}")
                all_match = False
                
    except Exception as e:
        print(f"\n❌ Fatal Connection Error: {e}")
        sys.exit(1)
        
    print("-" * 100)
    if all_match:
        print("🎉 SUCCESS: All tables match between MSSQL and ClickHouse Bronze.")
    else:
        print("⚠️ WARNING: Differences found. Please investigate specific tables.")

if __name__ == "__main__":
    main()
