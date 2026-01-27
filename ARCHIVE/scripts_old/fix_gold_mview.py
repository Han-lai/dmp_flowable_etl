#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正 Gold 層 MView - DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
"""

import clickhouse_connect
import time
from datetime import datetime

client = clickhouse_connect.get_client(
    host='10.136.218.207',
    port=8121,
    username='default',
    password='default'
)

print("=" * 80)
print("修正 Gold 層 MView")
print("=" * 80)
print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

try:
    # 步驟 1: 檢查 Gold MView 是否存在
    print("步驟 1: 檢查 DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV 是否存在")
    print("-" * 80)
    
    try:
        result = client.query('SHOW CREATE TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV')
        ddl = result.result_rows[0][0]
        
        print("當前 DDL:")
        print(ddl[:1000] + "...")
        
        # 檢查是否有 POPULATE
        has_populate = 'POPULATE' in ddl
        print(f"\nPOPULATE 關鍵字: {'✅ 存在' if has_populate else '❌ 缺失'}")
        
        table_exists = True
    except:
        print("❌ 表不存在，需要建立")
        table_exists = False
    
    # 步驟 2: 檢查來源表資料
    print("\n步驟 2: 檢查來源表資料")
    print("-" * 80)
    
    result = client.query('''
    SELECT 
        COUNT(*) as total_rows
    FROM silver.mv_l5_metrics_realtime
    ''')
    
    source_rows = result.result_rows[0][0]
    print(f"來源表 mv_l5_metrics_realtime: {source_rows} 行")
    
    if source_rows == 0:
        print("❌ 來源表無資料，無法填充 Gold MView")
        exit(1)
    
    # 步驟 3: 建立 Gold MView
    print(f"\n步驟 3: {'重建' if table_exists else '建立'} DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
    print("-" * 80)
    
    # 刪除舊 MView（如果存在）
    if table_exists:
        client.query("DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
        print("✅ 舊 MView 已刪除")
        time.sleep(2)
    
    # 重新建立 MView（添加 POPULATE）
    create_sql = """
CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
ENGINE = ReplacingMergeTree()
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT 
    toDate(now()) AS snapshot_date,
    COALESCE(plant, '') AS plant,
    COALESCE(factory, '') AS factory,
    COALESCE(line, '') AS line,
    vx_type,
    COALESCE(vx_subtype, '') AS vx_subtype,
    SUM(todo_qty) AS sum_todo_qty,
    SUM(doing_qty) AS sum_doing_qty,
    SUM(done_qty) AS sum_done_qty,
    SUM(total_task_qty) AS sum_total_task_qty,
    SUM(excluded_qty) AS sum_excluded_qty,
    CASE 
        WHEN SUM(total_task_qty) > 0 
        THEN ROUND(SUM(done_qty) * 100.0 / SUM(total_task_qty), 2)
        ELSE 0.0
    END AS completion_rate,
    now64(3) AS _mview_update_time
FROM silver.mv_l5_metrics_realtime
GROUP BY 
    plant,
    factory,
    line,
    vx_type,
    vx_subtype
"""
    
    client.query(create_sql)
    print("✅ 新 MView 已建立（包含 POPULATE）")
    
    time.sleep(3)
    
    # 步驟 4: 驗證資料
    print("\n步驟 4: 驗證 Gold MView 資料")
    print("-" * 80)
    
    result = client.query('''
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT plant) as plant_count,
        COUNT(DISTINCT factory) as factory_count,
        SUM(sum_total_task_qty) as sum_total_qty
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    ''')
    
    total, plants, factories, sum_total = result.result_rows[0]
    print(f"總行數: {total}")
    print(f"Plant 數: {plants}")
    print(f"Factory 數: {factories}")
    print(f"任務總數: {sum_total}")
    
    if total > 0:
        print("✅ Gold MView 已成功填充資料")
        
        # 查詢 Vx 類型分布
        result2 = client.query('''
        SELECT 
            vx_type,
            SUM(sum_total_task_qty) as count
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
        GROUP BY vx_type
        ORDER BY vx_type
        ''')
        
        print("\nVx 類型分布:")
        for row in result2.result_rows:
            vx_type, count = row
            print(f"  • {vx_type}: {count}")
            
        # 查詢 V1 子類型分布
        result3 = client.query('''
        SELECT 
            vx_subtype,
            SUM(sum_total_task_qty) as count
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
        WHERE vx_type = 'V1'
        GROUP BY vx_subtype
        ORDER BY vx_subtype
        ''')
        
        if result3.result_rows:
            print("\nV1 子類型分布:")
            for row in result3.result_rows:
                subtype, count = row
                print(f"  • {subtype}: {count}")
    else:
        print("❌ Gold MView 仍無資料")
    
    print("\n" + "=" * 80)
    print("✅ Gold 層修正完成")
    print("=" * 80)
    print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
except Exception as e:
    print(f"\n❌ 錯誤: {str(e)}")
    import traceback
    traceback.print_exc()