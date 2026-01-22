#!/usr/bin/env python3
"""
修正 Gold 層 MView 以支援歷史日期
問題：當前 MView 使用 toDate(now()) 只會產生當天資料
解決：改為使用 Silver 層的 snapshot_date 欄位
"""

import clickhouse_connect
from datetime import datetime

def main():
    print("=== 修正 Gold 層 MView 歷史日期支援 ===")
    
    # 連接 ClickHouse
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    # 1. 刪除現有的 Gold 層 MView
    print("\n1. 刪除現有的 Gold 層 MView...")
    
    drop_mview_sql = """
    DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    """
    
    try:
        client.command(drop_mview_sql)
        print("  ✅ 成功刪除現有 MView")
    except Exception as e:
        print(f"  ⚠️ 刪除 MView 時發生錯誤: {e}")
    
    # 2. 重新建立支援歷史日期的 MView
    print("\n2. 重新建立支援歷史日期的 MView...")
    
    create_mview_sql = """
    CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    ENGINE = ReplacingMergeTree()
    ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
    SETTINGS allow_nullable_key = 1
    POPULATE
    AS
    SELECT 
        snapshot_date,  -- 使用 Silver 層的實際日期，而不是 toDate(now())
        COALESCE(plant, '') AS plant,
        COALESCE(factory, '') AS factory,
        COALESCE(line, '') AS line,
        vx_type,
        COALESCE(vx_subtype, '') AS vx_subtype,
        
        -- 任務數量統計
        SUM(todo_qty) AS sum_todo_qty,
        SUM(doing_qty) AS sum_doing_qty,
        SUM(done_qty) AS sum_done_qty,
        SUM(total_task_qty) AS sum_total_task_qty,
        SUM(excluded_qty) AS sum_excluded_qty,
        
        -- 排除原因統計
        SUM(bypass_qty) AS sum_bypass_qty,
        SUM(e_prefix_qty) AS sum_e_prefix_qty,
        SUM(c_prefix_qty) AS sum_c_prefix_qty,
        SUM(q_order_qty) AS sum_q_order_qty,
        SUM(r_order_qty) AS sum_r_order_qty,
        
        -- 特殊規則統計
        SUM(special_v1_rule_qty) AS sum_special_v1_rule_qty,
        
        -- 完成率計算
        CASE 
            WHEN SUM(total_task_qty) > 0 
            THEN ROUND(SUM(done_qty) * 100.0 / SUM(total_task_qty), 2)
            ELSE 0.0
        END AS completion_rate,
        
        -- 進行中率計算
        CASE 
            WHEN SUM(total_task_qty) > 0 
            THEN ROUND((SUM(doing_qty) + SUM(done_qty)) * 100.0 / SUM(total_task_qty), 2)
            ELSE 0.0
        END AS progress_rate,
        
        now64(3) AS _mview_update_time
        
    FROM silver.mv_l5_metrics_realtime
    GROUP BY 
        snapshot_date,  -- 按實際日期分組
        plant,
        factory,
        line,
        vx_type,
        vx_subtype
    """
    
    try:
        client.command(create_mview_sql)
        print("  ✅ 成功建立新的 MView")
    except Exception as e:
        print(f"  ❌ 建立 MView 時發生錯誤: {e}")
        return
    
    # 3. 驗證新 MView 的資料
    print("\n3. 驗證新 MView 的資料...")
    
    verify_query = """
    SELECT 
        MIN(snapshot_date) as min_date,
        MAX(snapshot_date) as max_date,
        COUNT(DISTINCT snapshot_date) as date_count,
        COUNT(*) as total_rows
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
    """
    
    try:
        result = client.query(verify_query).result_rows[0]
        print(f"  日期範圍: {result[0]} ~ {result[1]}")
        print(f"  日期數量: {result[2]} 天")
        print(f"  總行數: {result[3]:,} 行")
    except Exception as e:
        print(f"  ❌ 驗證資料時發生錯誤: {e}")
        return
    
    # 4. 檢查 WJ2+NBU+E5 2025-12-30 的資料
    print("\n4. 檢查 WJ2+NBU+E5 2025-12-30 的資料...")
    
    wj2_query = """
    SELECT 
        snapshot_date,
        vx_type,
        vx_subtype,
        sum_total_task_qty,
        sum_todo_qty,
        sum_doing_qty,
        sum_done_qty,
        completion_rate
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND snapshot_date = '2025-12-30'
    ORDER BY vx_type, vx_subtype
    """
    
    try:
        wj2_results = client.query(wj2_query).result_rows
        if wj2_results:
            print("  ✅ 找到 WJ2+NBU+E5 2025-12-30 的資料:")
            print("  日期       | Vx | 子類型 | 總計 | TODO | DOING | DONE | 完成率")
            print("  " + "-" * 70)
            for result in wj2_results:
                print(f"  {result[0]} | {result[1]:2} | {result[2]:6} | {result[3]:4} | {result[4]:4} | {result[5]:5} | {result[6]:4} | {result[7]:6.1f}%")
        else:
            print("  ❌ 沒有找到 WJ2+NBU+E5 2025-12-30 的資料")
    except Exception as e:
        print(f"  ❌ 檢查 WJ2 資料時發生錯誤: {e}")
    
    # 5. 檢查各日期的資料分布
    print("\n5. 檢查各日期的資料分布...")
    
    date_dist_query = """
    SELECT 
        snapshot_date,
        COUNT(*) as row_count,
        SUM(sum_total_task_qty) as total_tasks
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
    GROUP BY snapshot_date
    ORDER BY snapshot_date DESC
    LIMIT 10
    """
    
    try:
        date_results = client.query(date_dist_query).result_rows
        print("  最近 10 天的資料分布:")
        print("  日期         | 行數 | 總任務數")
        print("  " + "-" * 35)
        for result in date_results:
            print(f"  {result[0]} | {result[1]:4} | {result[2]:8}")
    except Exception as e:
        print(f"  ❌ 檢查日期分布時發生錯誤: {e}")
    
    print("\n=== 修正完成 ===")
    print("✅ Gold 層 MView 現在支援歷史日期")
    print("✅ 可以進行 WJ2+NBU+E5 2025-12-30 的驗證")

if __name__ == '__main__':
    main()