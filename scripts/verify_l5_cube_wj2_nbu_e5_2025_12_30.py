#!/usr/bin/env python3
"""
驗證 L5 指標 Cube 是否能正確查詢 WJ2+NBU+E5 2025-12-30 的任務狀態
"""

import clickhouse_connect
from datetime import datetime

def main():
    print("=== 驗證 L5 指標 Cube - WJ2+NBU+E5 2025-12-30 ===")
    
    # 連接 ClickHouse (使用遠端服務器)
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    # 1. 檢查 Gold 層 MView 是否存在
    print("\n1. 檢查 Gold 層 MView 狀態...")
    
    gold_tables_query = """
    SELECT 
        name,
        engine,
        total_rows,
        total_bytes
    FROM system.tables 
    WHERE database = 'gold' 
      AND engine LIKE '%View%'
    ORDER BY name
    """
    
    gold_tables = client.query(gold_tables_query).result_rows
    print(f"Gold 層 MView 數量: {len(gold_tables)}")
    for table in gold_tables:
        print(f"  - {table[0]}: {table[1]}, {table[2]:,} 行")
    
    # 2. 檢查 Silver 層 MView 資料
    print("\n2. 檢查 Silver 層 MView 資料...")
    
    silver_query = """
    SELECT 
        'mv_fact_task_vx_attribution' as table_name,
        COUNT(*) as total_rows,
        COUNT(CASE WHEN plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' THEN 1 END) as wj2_nbu_e5_rows,
        COUNT(CASE WHEN plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
                   AND toDate(task_create_time) = '2025-12-30' THEN 1 END) as target_date_rows
    FROM silver.mv_fact_task_vx_attribution FINAL
    
    UNION ALL
    
    SELECT 
        'mv_l5_metrics_realtime' as table_name,
        COUNT(*) as total_rows,
        COUNT(CASE WHEN plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' THEN 1 END) as wj2_nbu_e5_rows,
        COUNT(CASE WHEN plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
                   AND snapshot_date = '2025-12-30' THEN 1 END) as target_date_rows
    FROM silver.mv_l5_metrics_realtime FINAL
    """
    
    silver_results = client.query(silver_query).result_rows
    for result in silver_results:
        print(f"  {result[0]}: 總計 {result[1]:,} 行, WJ2+NBU+E5 {result[2]:,} 行, 目標日期 {result[3]:,} 行")
    
    # 3. 直接查詢 WJ2+NBU+E5 2025-12-30 的任務狀態分布
    print("\n3. 查詢 WJ2+NBU+E5 2025-12-30 任務狀態分布...")
    
    task_status_query = """
    SELECT 
        vx_type,
        vx_subtype,
        task_status,
        COUNT(*) as task_count,
        COUNT(CASE WHEN is_excluded = 0 THEN 1 END) as included_count,
        COUNT(CASE WHEN is_excluded = 1 THEN 1 END) as excluded_count
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE plant = 'WJ2' 
      AND factory = 'NBU' 
      AND line = 'E5'
      AND toDate(task_create_time) = '2025-12-30'
    GROUP BY vx_type, vx_subtype, task_status
    ORDER BY vx_type, vx_subtype, task_status
    """
    
    task_results = client.query(task_status_query).result_rows
    if task_results:
        print("  Vx類型 | 子類型 | 狀態 | 總數 | 未排除 | 已排除")
        print("  " + "-" * 50)
        for result in task_results:
            vx_type = result[0] or 'NULL'
            vx_subtype = result[1] or 'NULL'
            task_status = result[2] or 'NULL'
            print(f"  {vx_type:6} | {vx_subtype:6} | {task_status:4} | {result[3]:4} | {result[4]:6} | {result[5]:6}")
    else:
        print("  ❌ 沒有找到 WJ2+NBU+E5 2025-12-30 的任務資料")
    
    # 4. 檢查 Gold 層是否有對應資料
    print("\n4. 檢查 Gold 層 MView 資料...")
    
    # 檢查是否存在 Gold 層表
    gold_check_query = """
    SELECT name 
    FROM system.tables 
    WHERE database = 'gold' 
      AND name LIKE '%L5%' 
      AND engine LIKE '%View%'
    """
    
    gold_tables_list = client.query(gold_check_query).result_rows
    if gold_tables_list:
        gold_table_name = gold_tables_list[0][0]
        print(f"  找到 Gold 層表: {gold_table_name}")
        
        gold_data_query = f"""
        SELECT 
            snapshot_date,
            vx_type,
            vx_subtype,
            plant,
            factory,
            line,
            sum_total_task_qty,
            sum_todo_qty,
            sum_doing_qty,
            sum_done_qty
        FROM gold.{gold_table_name} FINAL
        WHERE plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND snapshot_date = '2025-12-30'
        ORDER BY vx_type, vx_subtype
        """
        
        gold_results = client.query(gold_data_query).result_rows
        if gold_results:
            print("  日期 | Vx類型 | 子類型 | 廠區 | 總數 | TODO | DOING | DONE")
            print("  " + "-" * 70)
            for result in gold_results:
                print(f"  {result[0]} | {result[1]:6} | {result[2] or 'NULL':6} | {result[3]}-{result[4]}-{result[5]} | {result[6]:4} | {result[7]:4} | {result[8]:5} | {result[9]:4}")
        else:
            print("  ❌ Gold 層沒有找到 WJ2+NBU+E5 2025-12-30 的資料")
    else:
        print("  ❌ 沒有找到 Gold 層 L5 相關的 MView")
    
    # 5. 模擬 Cube 查詢
    print("\n5. 模擬 Cube 查詢邏輯...")
    
    cube_simulation_query = """
    SELECT 
        toDate(task_create_time) AS snapshot_date,
        vx_type,
        vx_subtype,
        plant,
        factory,
        line,
        
        -- L5 核心指標 (模擬 Cube measures)
        COUNT(CASE WHEN is_excluded = 0 THEN 1 END) AS totalTasks,
        COUNT(CASE WHEN is_excluded = 0 AND task_status = 'TODO' THEN 1 END) AS todoTasks,
        COUNT(CASE WHEN is_excluded = 0 AND task_status = 'DOING' THEN 1 END) AS doingTasks,
        COUNT(CASE WHEN is_excluded = 0 AND task_status = 'DONE' THEN 1 END) AS doneTasks,
        COUNT(CASE WHEN is_excluded = 1 THEN 1 END) AS excludedTasks,
        
        -- 完成率計算
        CASE 
            WHEN COUNT(CASE WHEN is_excluded = 0 THEN 1 END) > 0 
            THEN ROUND(COUNT(CASE WHEN is_excluded = 0 AND task_status = 'DONE' THEN 1 END) * 100.0 / 
                       COUNT(CASE WHEN is_excluded = 0 THEN 1 END), 2)
            ELSE 0.0
        END AS completionRate
        
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE plant = 'WJ2' 
      AND factory = 'NBU' 
      AND line = 'E5'
      AND toDate(task_create_time) = '2025-12-30'
    GROUP BY snapshot_date, vx_type, vx_subtype, plant, factory, line
    ORDER BY vx_type, vx_subtype
    """
    
    cube_results = client.query(cube_simulation_query).result_rows
    if cube_results:
        print("  模擬 Cube 查詢結果:")
        print("  日期 | Vx | 子類型 | 總數 | TODO | DOING | DONE | 排除 | 完成率%")
        print("  " + "-" * 80)
        for result in cube_results:
            print(f"  {result[0]} | {result[1]:2} | {result[2] or 'NULL':6} | {result[6]:4} | {result[7]:4} | {result[8]:5} | {result[9]:4} | {result[10]:4} | {result[11]:7.2f}")
    else:
        print("  ❌ 模擬 Cube 查詢沒有結果")
    
    # 6. 總結
    print("\n=== 驗證總結 ===")
    if task_results and len(task_results) > 0:
        total_tasks = sum(r[3] for r in task_results)
        included_tasks = sum(r[4] for r in task_results)
        excluded_tasks = sum(r[5] for r in task_results)
        print(f"✅ 找到 WJ2+NBU+E5 2025-12-30 的任務資料")
        print(f"   總任務數: {total_tasks}")
        print(f"   未排除任務數: {included_tasks}")
        print(f"   已排除任務數: {excluded_tasks}")
        
        if cube_results:
            print(f"✅ Cube 查詢邏輯正常")
        else:
            print(f"❌ Cube 查詢邏輯有問題")
    else:
        print(f"❌ 沒有找到目標資料，請檢查:")
        print(f"   1. Silver 層 MView 是否有資料")
        print(f"   2. 日期/廠區條件是否正確")
        print(f"   3. 資料同步是否完成")

if __name__ == '__main__':
    main()