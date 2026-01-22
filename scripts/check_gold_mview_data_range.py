#!/usr/bin/env python3
"""
檢查 Gold 層 MView 的資料範圍和內容
"""

import clickhouse_connect
from datetime import datetime

def main():
    print("=== 檢查 Gold 層 MView 資料範圍 ===")
    
    # 連接 ClickHouse (使用遠端服務器)
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    # 1. 檢查 Gold 層 MView 的日期範圍
    print("\n1. 檢查 Gold 層 MView 日期範圍...")
    
    date_range_query = """
    SELECT 
        MIN(snapshot_date) as min_date,
        MAX(snapshot_date) as max_date,
        COUNT(DISTINCT snapshot_date) as date_count,
        COUNT(*) as total_rows
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
    """
    
    result = client.query(date_range_query).result_rows[0]
    print(f"  日期範圍: {result[0]} ~ {result[1]}")
    print(f"  日期數量: {result[2]} 天")
    print(f"  總行數: {result[3]:,} 行")
    
    # 2. 檢查是否有 WJ2+NBU+E5 的資料
    print("\n2. 檢查 WJ2+NBU+E5 資料...")
    
    wj2_query = """
    SELECT 
        snapshot_date,
        COUNT(*) as row_count,
        SUM(sum_total_task_qty) as total_tasks
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    GROUP BY snapshot_date
    ORDER BY snapshot_date DESC
    LIMIT 10
    """
    
    wj2_results = client.query(wj2_query).result_rows
    if wj2_results:
        print("  WJ2+NBU+E5 最近 10 天的資料:")
        print("  日期         | 行數 | 總任務數")
        print("  " + "-" * 35)
        for result in wj2_results:
            print(f"  {result[0]} | {result[1]:4} | {result[2]:8}")
    else:
        print("  ❌ 沒有找到 WJ2+NBU+E5 的資料")
    
    # 3. 檢查 Gold 層 MView 的更新邏輯
    print("\n3. 檢查 Gold 層 MView 定義...")
    
    mview_def_query = """
    SELECT create_table_query
    FROM system.tables
    WHERE database = 'gold' 
      AND name = 'DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV'
    """
    
    mview_def = client.query(mview_def_query).result_rows
    if mview_def:
        create_sql = mview_def[0][0]
        print("  MView 定義片段:")
        # 只顯示關鍵部分
        lines = create_sql.split('\n')
        for i, line in enumerate(lines):
            if 'SELECT' in line or 'FROM' in line or 'GROUP BY' in line:
                print(f"    {line.strip()}")
                if i < len(lines) - 1:
                    print(f"    {lines[i+1].strip()}")
                break
    
    # 4. 檢查 Silver 層對應的資料
    print("\n4. 檢查 Silver 層對應資料...")
    
    silver_query = """
    SELECT 
        toDate(now()) as today_date,
        COUNT(*) as total_rows,
        COUNT(CASE WHEN plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' THEN 1 END) as wj2_rows,
        COUNT(CASE WHEN plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
                   AND snapshot_date = '2025-12-30' THEN 1 END) as target_date_rows
    FROM silver.mv_l5_metrics_realtime FINAL
    """
    
    silver_result = client.query(silver_query).result_rows[0]
    print(f"  今天日期: {silver_result[0]}")
    print(f"  Silver 層總行數: {silver_result[1]:,}")
    print(f"  WJ2+NBU+E5 行數: {silver_result[2]:,}")
    print(f"  2025-12-30 目標行數: {silver_result[3]:,}")
    
    # 5. 檢查 Gold 層 MView 的 SQL 邏輯
    print("\n5. 模擬 Gold 層 MView 邏輯...")
    
    gold_simulation_query = """
    SELECT 
        toDate(now()) AS snapshot_date,
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
        SUM(excluded_qty) AS sum_excluded_qty
        
    FROM silver.mv_l5_metrics_realtime FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND snapshot_date = '2025-12-30'
    GROUP BY 
        plant,
        factory,
        line,
        vx_type,
        vx_subtype
    ORDER BY vx_type, vx_subtype
    """
    
    gold_sim_results = client.query(gold_simulation_query).result_rows
    if gold_sim_results:
        print("  模擬 Gold 層結果:")
        print("  日期 | 廠區 | Vx | 子類型 | TODO | DOING | DONE | 總計")
        print("  " + "-" * 65)
        for result in gold_sim_results:
            print(f"  {result[0]} | {result[1]}-{result[2]}-{result[3]} | {result[4]:2} | {result[5]:6} | {result[6]:4} | {result[7]:5} | {result[8]:4} | {result[9]:4}")
    else:
        print("  ❌ 模擬 Gold 層查詢沒有結果")
        
        # 檢查 Silver 層是否有對應日期的資料
        silver_check_query = """
        SELECT 
            snapshot_date,
            COUNT(*) as row_count
        FROM silver.mv_l5_metrics_realtime FINAL
        WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        GROUP BY snapshot_date
        ORDER BY snapshot_date DESC
        LIMIT 5
        """
        
        silver_check_results = client.query(silver_check_query).result_rows
        print("\n  Silver 層 WJ2+NBU+E5 最近的日期:")
        for result in silver_check_results:
            print(f"    {result[0]}: {result[1]} 行")
    
    print("\n=== 總結 ===")
    print("Gold 層 MView 可能的問題:")
    print("1. MView 使用 toDate(now()) 作為 snapshot_date，只會產生當天的資料")
    print("2. 需要修改 MView 邏輯以支援歷史日期")
    print("3. 或者需要手動觸發 MView 更新以包含歷史資料")

if __name__ == '__main__':
    main()