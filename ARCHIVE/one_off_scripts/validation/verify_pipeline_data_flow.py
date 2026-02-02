#!/usr/bin/env python3
"""
Verify Data Pipeline Flow (Bronze -> Silver -> Gold)
====================================================
1. Checks data freshness in Bronze (Source).
2. Checks data freshness in Silver (MView - should auto-update).
3. Refreshes Gold Layer (Snapshot Table - requires manual update).
4. Verifies data counts and max dates across all layers.
"""

import clickhouse_connect
import time
import sys

# ClickHouse Config
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    print("🚀 Starting Pipeline Data Flow Validation")
    print("=" * 60)
    
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        print("✅ Connected to ClickHouse")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)

    # 1. Check Bronze Freshness
    print("\n📊 Checking Bronze Layer Freshness (bpm_act_hi_taskinst)...")
    bronze_stats = client.query("SELECT count(*), max(toDateTime(START_TIME_)) FROM bronze.bpm_act_hi_taskinst").result_rows[0]
    print(f"   Bronze Rows: {bronze_stats[0]:,}")
    print(f"   Bronze Latest Task Time: {bronze_stats[1]}")

    # 2. Check Silver Freshness
    print("\n📊 Checking Silver Layer Freshness (mv_fact_task_vx_attribution_mdm)...")
    silver_stats = client.query("SELECT count(*), max(task_create_time) FROM silver.mv_fact_task_vx_attribution_mdm").result_rows[0]
    print(f"   Silver MView Rows: {silver_stats[0]:,}")
    print(f"   Silver Latest Task Time: {silver_stats[1]}")

    # 3. Refresh Gold Layer
    print("\n🔄 Refreshing Gold Layer (l5_dashboard_summary)...")
    start_time = time.perf_counter()
    
    try:
        client.command("TRUNCATE TABLE gold.l5_dashboard_summary")
        client.command("INSERT INTO gold.l5_dashboard_summary SELECT * FROM gold.v_l5_dashboard_summary_populate")
        duration = time.perf_counter() - start_time
        print(f"✅ Gold Layer Refreshed in {duration:.2f} seconds")
    except Exception as e:
        print(f"❌ Gold Refresh Failed: {e}")
        sys.exit(1)

    # 4. Verify Gold Data
    print("\n📊 Checking Gold Layer Freshness (l5_dashboard_summary)...")
    gold_stats = client.query("SELECT sum(total_task), max(snapshot_date) FROM gold.l5_dashboard_summary").result_rows[0]
    print(f"   Gold Total Tasks: {gold_stats[0]:,}")
    print(f"   Gold Latest Snapshot: {gold_stats[1]}")

    # 5. Specific Verification (WJ2/NBU)
    print("\n🔍 Verifying Specific Scope (WJ2 / NBU)...")
    scope_check = client.query("""
        SELECT 
            snapshot_date, 
            factory, 
            sum(total_task) 
        FROM gold.l5_dashboard_summary 
        WHERE plant = 'WJ2' AND factory = 'NBU' 
        GROUP BY snapshot_date, factory 
        ORDER BY snapshot_date DESC 
        LIMIT 5
    """)
    
    if scope_check.result_rows:
        print("   Found data for WJ2/NBU:")
        for row in scope_check.result_rows:
            print(f"   - {row[0]}: {row[1]} = {row[2]} tasks")
    else:
        print("⚠️ No data found for WJ2/NBU in Gold layer!")

    print("\n" + "=" * 60)
    print("✅ Pipeline Verification Completed")

if __name__ == "__main__":
    main()
