#!/usr/bin/env python3
"""
Gold 層 View 部署腳本
====================
部署 gold.v_l5_dashboard_summary_populate 視圖，以便進行金層快照更新。
"""

import clickhouse_connect
import sys

# ClickHouse 連線設定
CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    print("=" * 80)
    print("🚀 正在部署 Gold 層 Populate View")
    print("=" * 80)

    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        view_sql = """
        CREATE OR REPLACE VIEW gold.v_l5_dashboard_summary_populate AS
        SELECT
            task_create_date AS snapshot_date,
            vx_type,
            
            -- 使用 Silver 層補齊後的完整五階維度
            region,
            plant,
            factory,
            line,
            
            -- 維度資料來源追蹤
            region_source,
            plant_source,
            factory_source,
            line_source,
            dimension_source,
            
            -- 任務統計
            COUNT(*) AS total_task,
            countIf(task_status = 'TODO') AS todo_task,
            countIf(task_status = 'DOING') AS doing_task,
            countIf(task_status = 'DONE') AS done_task,
            
            -- 完成率
            CASE 
                WHEN COUNT(*) > 0 
                THEN countIf(task_status = 'DONE') * 100.0 / COUNT(*)
                ELSE 0
            END AS completion_rate,
            
            -- 維度資料品質統計
            countIf(region_source = 'MDM') AS region_mdm_backfill_count,
            countIf(plant_source = 'MDM') AS plant_mdm_backfill_count,
            countIf(factory_source = 'MDM') AS factory_mdm_backfill_count,
            countIf(line_source = 'MDM') AS line_mdm_backfill_count,
            
            -- Metadata
            1 AS _version,
            now64(3) AS _update_time

        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE is_excluded = 0
          AND task_create_date >= '2025-01-01'
        GROUP BY 
            task_create_date, vx_type, region, plant, factory, line,
            region_source, plant_source, factory_source, line_source, dimension_source;
        """
        
        print("正在執行 CREATE VIEW...")
        client.command(view_sql)
        print("✅ Gold 視圖部署成功！")
        
    except Exception as e:
        print(f"\n❌ 部署失敗: {e}")
        sys.exit(1)

    print("=" * 80)
    print("💡 現在你可以重新執行更新腳本了：")
    print("python scripts/etl/update_gold_layer.py")
    print("=" * 80)

if __name__ == "__main__":
    main()
