#!/usr/bin/env python3
"""
調查 CNE WJ2 NBU E5 2025-12-25 資料問題
Superset 只顯示 doing=1，但應該有 todo=4

檢查點：
1. ClickHouse Gold 層資料
2. ClickHouse Silver 層資料
3. Cube.js 查詢結果
4. 資料管道完整性
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect
import pandas as pd
from datetime import datetime

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def check_gold_layer_data(client, test_date='2025-12-25'):
    """檢查 Gold 層資料"""
    print(f"\n🔍 檢查 Gold 層資料 - {test_date}")
    print("=" * 60)
    
    query = f"""
    SELECT 
        snapshot_date,
        region,
        plant,
        factory,
        line,
        vx_type,
        total_task,
        todo_task,
        doing_task,
        done_task,
        completion_rate,
        dimension_source,
        region_source,
        plant_source,
        factory_source,
        line_source,
        _update_time
    FROM gold.l5_dashboard_summary FINAL
    WHERE snapshot_date = '{test_date}'
      AND region = 'CNE'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    ORDER BY vx_type
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        if len(df) == 0:
            print("❌ Gold 層沒有找到符合條件的資料")
            return None
        
        print(f"✅ Gold 層找到 {len(df)} 筆資料:")
        for _, row in df.iterrows():
            print(f"  VX={row['vx_type']}: Total={row['total_task']}, Todo={row['todo_task']}, Doing={row['doing_task']}, Done={row['done_task']}")
            print(f"    維度來源: {row['dimension_source']}, Region={row['region_source']}, Plant={row['plant_source']}")
            print(f"    更新時間: {row['_update_time']}")
        
        return df
        
    except Exception as e:
        print(f"❌ Gold 層查詢失敗: {e}")
        return None

def check_silver_layer_data(client, test_date='2025-12-25'):
    """檢查 Silver 層原始資料"""
    print(f"\n🔍 檢查 Silver 層資料 - {test_date}")
    print("=" * 60)
    
    query = f"""
    SELECT 
        vx_type,
        region,
        plant,
        factory,
        line,
        task_status,
        COUNT(*) as task_count,
        COUNT(DISTINCT proc_inst_id) as proc_count
    FROM silver.mv_fact_task_vx_attribution_mdm FINAL
    WHERE (
        toDate(task_create_time) = '{test_date}'
        OR toDate(task_claim_time) = '{test_date}'
        OR toDate(task_end_time) = '{test_date}'
    )
      AND region = 'CNE'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
      AND is_excluded = 0
    GROUP BY vx_type, region, plant, factory, line, task_status
    ORDER BY vx_type, task_status
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        if len(df) == 0:
            print("❌ Silver 層沒有找到符合條件的資料")
            return None
        
        print(f"✅ Silver 層找到 {len(df)} 筆聚合資料:")
        for _, row in df.iterrows():
            print(f"  VX={row['vx_type']}, Status={row['task_status']}: {row['task_count']} 任務 ({row['proc_count']} 流程)")
        
        return df
        
    except Exception as e:
        print(f"❌ Silver 層查詢失敗: {e}")
        return None

def check_detailed_silver_data(client, test_date='2025-12-25'):
    """檢查 Silver 層詳細資料"""
    print(f"\n🔍 檢查 Silver 層詳細資料 - {test_date}")
    print("=" * 60)
    
    query = f"""
    SELECT 
        proc_inst_id,
        task_id,
        vx_type,
        task_status,
        region,
        plant,
        factory,
        line,
        region_source,
        plant_source,
        factory_source,
        line_source,
        task_create_time,
        task_claim_time,
        task_end_time,
        is_excluded
    FROM silver.mv_fact_task_vx_attribution_mdm FINAL
    WHERE (
        toDate(task_create_time) = '{test_date}'
        OR toDate(task_claim_time) = '{test_date}'
        OR toDate(task_end_time) = '{test_date}'
    )
      AND region = 'CNE'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    ORDER BY vx_type, task_status, task_create_time
    LIMIT 20
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        if len(df) == 0:
            print("❌ Silver 層詳細資料沒有找到符合條件的資料")
            return None
        
        print(f"✅ Silver 層詳細資料找到 {len(df)} 筆 (顯示前20筆):")
        for _, row in df.iterrows():
            excluded_mark = "❌" if row['is_excluded'] else "✅"
            print(f"  {excluded_mark} VX={row['vx_type']}, Status={row['task_status']}")
            print(f"    Task: {row['task_id'][:8]}...")
            print(f"    維度: {row['region']}-{row['plant']}-{row['factory']}-{row['line']}")
            print(f"    來源: R={row['region_source']}, P={row['plant_source']}, F={row['factory_source']}, L={row['line_source']}")
            print(f"    時間: Create={row['task_create_time']}, Claim={row['task_claim_time']}, End={row['task_end_time']}")
            print()
        
        return df
        
    except Exception as e:
        print(f"❌ Silver 層詳細查詢失敗: {e}")
        return None

def check_cube_aggregation(client, test_date='2025-12-25'):
    """模擬 Cube.js 聚合邏輯"""
    print(f"\n🔍 模擬 Cube.js 聚合邏輯 - {test_date}")
    print("=" * 60)
    
    # 模擬 Cube.js 的聚合查詢
    query = f"""
    SELECT 
        snapshot_date,
        region,
        plant,
        factory,
        line,
        vx_type,
        SUM(total_task) as total_task,
        SUM(todo_task) as todo_task,
        SUM(doing_task) as doing_task,
        SUM(done_task) as done_task,
        AVG(completion_rate) as avg_completion_rate
    FROM gold.l5_dashboard_summary FINAL
    WHERE snapshot_date = '{test_date}'
      AND region = 'CNE'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    GROUP BY snapshot_date, region, plant, factory, line, vx_type
    ORDER BY vx_type
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        if len(df) == 0:
            print("❌ Cube.js 模擬聚合沒有資料")
            return None
        
        print(f"✅ Cube.js 模擬聚合結果 ({len(df)} 筆):")
        for _, row in df.iterrows():
            print(f"  VX={row['vx_type']}: Total={row['total_task']}, Todo={row['todo_task']}, Doing={row['doing_task']}, Done={row['done_task']}")
            print(f"    完成率: {row['avg_completion_rate']:.1f}%")
        
        return df
        
    except Exception as e:
        print(f"❌ Cube.js 模擬聚合失敗: {e}")
        return None

def check_data_pipeline_integrity(client, test_date='2025-12-25'):
    """檢查資料管道完整性"""
    print(f"\n🔍 檢查資料管道完整性 - {test_date}")
    print("=" * 60)
    
    # 檢查各層資料數量
    layers = [
        ("Bronze", "bronze.bpm_act_hi_taskinst", "START_TIME_"),
        ("Silver", "silver.mv_fact_task_vx_attribution_mdm", "task_create_time"),
        ("Gold", "gold.l5_dashboard_summary", "snapshot_date")
    ]
    
    for layer_name, table_name, date_field in layers:
        if layer_name == "Gold":
            query = f"""
            SELECT COUNT(*) as record_count
            FROM {table_name} FINAL
            WHERE {date_field} = '{test_date}'
              AND region = 'CNE'
              AND plant = 'WJ2'
              AND factory = 'NBU'
              AND line = 'E5'
            """
        else:
            query = f"""
            SELECT COUNT(*) as record_count
            FROM {table_name} FINAL
            WHERE toDate({date_field}) = '{test_date}'
            """
            
            if layer_name == "Silver":
                query += """
                  AND region = 'CNE'
                  AND plant = 'WJ2'
                  AND factory = 'NBU'
                  AND line = 'E5'
                """
        
        try:
            result = client.query(query)
            count = result.result_rows[0][0]
            print(f"  {layer_name} 層 ({table_name}): {count} 筆記錄")
        except Exception as e:
            print(f"  ❌ {layer_name} 層查詢失敗: {e}")

def main():
    """主執行函數"""
    print("🚀 調查 CNE WJ2 NBU E5 2025-12-25 Superset 資料問題")
    print("📋 問題：Superset 只顯示 doing=1，但應該有 todo=4")
    print("=" * 80)
    
    # 建立連線
    client = get_clickhouse_client()
    if client is None:
        return False
    
    test_date = '2025-12-25'
    
    # 1. 檢查 Gold 層資料
    gold_df = check_gold_layer_data(client, test_date)
    
    # 2. 檢查 Silver 層聚合資料
    silver_df = check_silver_layer_data(client, test_date)
    
    # 3. 檢查 Silver 層詳細資料
    detailed_df = check_detailed_silver_data(client, test_date)
    
    # 4. 模擬 Cube.js 聚合
    cube_df = check_cube_aggregation(client, test_date)
    
    # 5. 檢查資料管道完整性
    check_data_pipeline_integrity(client, test_date)
    
    # 分析結果
    print(f"\n📊 問題分析")
    print("=" * 60)
    
    if gold_df is not None and len(gold_df) > 0:
        total_todo = gold_df['todo_task'].sum()
        total_doing = gold_df['doing_task'].sum()
        total_done = gold_df['done_task'].sum()
        
        print(f"Gold 層彙總: Todo={total_todo}, Doing={total_doing}, Done={total_done}")
        
        if total_todo == 0 and total_doing == 1:
            print("⚠️ 問題確認：Gold 層確實只有 doing=1，沒有 todo 資料")
            print("🔍 可能原因：")
            print("1. Silver 層資料聚合邏輯問題")
            print("2. 日期篩選條件問題")
            print("3. 維度對應問題")
            print("4. 任務狀態判斷邏輯問題")
        elif total_todo > 0:
            print("✅ Gold 層有 todo 資料，問題可能在 Superset 或 Cube.js")
        
    else:
        print("❌ Gold 層沒有資料，問題在資料管道上游")
    
    # 清理連線
    try:
        client.close()
    except:
        pass
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)