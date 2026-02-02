#!/usr/bin/env python3
"""
Gold 層全自動化升級腳本
========================
將 gold.l5_dashboard_summary 從手動快照表升級為全自動 Materialized View 指標流。

架構：
1. gold.l5_dashboard_summary_base (SummingMergeTree): 儲存聚合後的數值基礎表
2. gold.mv_l5_dashboard_summary (Materialized View): 自動從 Silver 層聚合並更新 Base 表
3. gold.l5_dashboard_summary (View): 最終消費視圖，計算百分比並提供給 Cube.js
"""

import clickhouse_connect
import sys
import time
from datetime import datetime

# ClickHouse 連線設定
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    print("=" * 80)
    print("🚀 啟動 Gold 層全自動化流升級")
    print(f"   執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        # 1. 清理舊有結構
        print("1. 清理舊有 Gold 層結構 (Table/View)...")
        client.command("DROP TABLE IF EXISTS gold.l5_dashboard_summary")
        client.command("DROP TABLE IF EXISTS gold.l5_dashboard_summary_base")
        client.command("DROP VIEW IF EXISTS gold.mv_l5_dashboard_summary")
        client.command("DROP VIEW IF EXISTS gold.v_l5_dashboard_summary_populate")
        
        # 2. 建立新的基礎表 (SummingMergeTree)
        # 用於儲存聚合後的 count 數值
        print("2. 建立聚合基礎表 (SummingMergeTree)...")
        create_base_table = """
        CREATE TABLE gold.l5_dashboard_summary_base
        (
            snapshot_date Date,
            vx_type LowCardinality(String),
            region String,
            plant String,
            factory String,
            line String,
            region_source String,
            plant_source String,
            factory_source String,
            line_source String,
            dimension_source String,
            
            -- 需要被加總的指標
            total_task Int64,
            todo_task Int64,
            doing_task Int64,
            done_task Int64,
            
            -- 維度品質統計
            region_mdm_backfill_count Int64,
            plant_mdm_backfill_count Int64,
            factory_mdm_backfill_count Int64,
            line_mdm_backfill_count Int64,
            
            _update_time DateTime64(3)
        )
        ENGINE = SummingMergeTree(_update_time)
        ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
        """
        client.command(create_base_table)

        # 3. 建立自動觸發的 Materialized View
        print("3. 建立自動觸發 Materialized View...")
        create_mview = """
        CREATE MATERIALIZED VIEW gold.mv_l5_dashboard_summary
        TO gold.l5_dashboard_summary_base
        AS
        SELECT
            task_create_date AS snapshot_date,
            vx_type,
            region,
            plant,
            factory,
            line,
            region_source,
            plant_source,
            factory_source,
            line_source,
            dimension_source,
            
            COUNT(*) AS total_task,
            countIf(task_status = 'TODO') AS todo_task,
            countIf(task_status = 'DOING') AS doing_task,
            countIf(task_status = 'DONE') AS done_task,
            
            countIf(region_source = 'MDM') AS region_mdm_backfill_count,
            countIf(plant_source = 'MDM') AS plant_mdm_backfill_count,
            countIf(factory_source = 'MDM') AS factory_mdm_backfill_count,
            countIf(line_source = 'MDM') AS line_mdm_backfill_count,
            
            now64(3) AS _update_time
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE is_excluded = 0
        GROUP BY 
            snapshot_date, vx_type, region, plant, factory, line,
            region_source, plant_source, factory_source, line_source, dimension_source
        """
        client.command(create_mview)

        # 4. 建立最終消費視圖 (View)
        # 用於計算計算型指標如完成率，並提供給 Cube.js
        print("4. 建立最終消費視圖 (計算完成率)...")
        create_final_view = """
        CREATE VIEW gold.l5_dashboard_summary AS
        SELECT
            snapshot_date,
            vx_type,
            region,
            plant,
            factory,
            line,
            region_source,
            plant_source,
            factory_source,
            line_source,
            dimension_source,
            
            -- 聚合後的數值
            sum(total_task) AS total_task,
            sum(todo_task) AS todo_task,
            sum(doing_task) AS doing_task,
            sum(done_task) AS done_task,
            
            -- 動態計算比例
            CASE 
                WHEN sum(total_task) > 0 
                THEN sum(done_task) * 100.0 / sum(total_task)
                ELSE 0
            END AS completion_rate,
            
            sum(region_mdm_backfill_count) AS region_mdm_backfill_count,
            sum(plant_mdm_backfill_count) AS plant_mdm_backfill_count,
            sum(factory_mdm_backfill_count) AS factory_mdm_backfill_count,
            sum(line_mdm_backfill_count) AS line_mdm_backfill_count,
            
            max(_update_time) AS _update_time
        FROM gold.l5_dashboard_summary_base
        GROUP BY 
            snapshot_date, vx_type, region, plant, factory, line,
            region_source, plant_source, factory_source, line_source, dimension_source
        """
        client.command(create_final_view)

        # 5. 初始資料導入 (POPULATE)
        print("5. 初始資料導入中 (從 Silver 同步既存資料)...")
        start_time = time.perf_counter()
        
        # 由於 ClickHouse 24.3+ 建議手動 INSERT 以避免大規模 POPULATE 鎖表
        populate_sql = """
        INSERT INTO gold.l5_dashboard_summary_base
        SELECT
            task_create_date AS snapshot_date,
            vx_type,
            region,
            plant,
            factory,
            line,
            region_source,
            plant_source,
            factory_source,
            line_source,
            dimension_source,
            
            COUNT(*) AS total_task,
            countIf(task_status = 'TODO') AS todo_task,
            countIf(task_status = 'DOING') AS doing_task,
            countIf(task_status = 'DONE') AS done_task,
            
            countIf(region_source = 'MDM') AS region_mdm_backfill_count,
            countIf(plant_source = 'MDM') AS plant_mdm_backfill_count,
            countIf(factory_source = 'MDM') AS factory_mdm_backfill_count,
            countIf(line_source = 'MDM') AS line_mdm_backfill_count,
            
            now64(3) AS _update_time
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE is_excluded = 0
          AND task_create_date >= '2025-01-01'
        GROUP BY 
            snapshot_date, vx_type, region, plant, factory, line,
            region_source, plant_source, factory_source, line_source, dimension_source
        """
        client.command(populate_sql)
        
        duration = time.perf_counter() - start_time
        count = client.command("SELECT count(*) FROM gold.l5_dashboard_summary")
        
        print(f"\n✅ 升級成功！")
        print(f"   初始資料筆數: {count:,}")
        print(f"   耗時: {duration:.2f} 秒")
        print("-" * 80)
        print("💡 目前資料流已切換為：")
        print("   Silver (INSERT) -> Gold MVIEW (AUTO) -> Gold Base (Summing) -> Cube.js (View)")
        
    except Exception as e:
        print(f"\n❌ 升級過程發生錯誤: {e}")
        sys.exit(1)

    print("=" * 80)

if __name__ == "__main__":
    main()
