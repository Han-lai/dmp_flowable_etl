#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建 mv_l5_metrics_realtime，包含最新的 NPE 資料
"""

import clickhouse_connect
import time
from datetime import datetime

client = clickhouse_connect.get_client(
    host='REDACTED_IP',
    port=8121,
    username='default',
    password='default'
)

print("=" * 80)
print("重建 mv_l5_metrics_realtime")
print("=" * 80)
print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

try:
    # 步驟 1: 刪除舊 MView
    print("步驟 1: 刪除舊的 mv_l5_metrics_realtime")
    print("-" * 80)
    
    client.query("DROP TABLE IF EXISTS silver.mv_l5_metrics_realtime")
    print("✅ 舊 MView 已刪除")
    
    time.sleep(2)
    
    # 步驟 2: 重建 MView
    print("\n步驟 2: 重建 mv_l5_metrics_realtime（包含 NPE 邏輯）")
    print("-" * 80)
    
    create_sql = """
CREATE MATERIALIZED VIEW silver.mv_l5_metrics_realtime
ENGINE = SummingMergeTree()
ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    toDate(task_create_time) AS snapshot_date,
    vx_type,
    vx_subtype,
    plant,
    factory,
    line,
    
    -- 基礎統計（只計算未排除的任務）
    countIf(is_excluded = 0) AS total_task_qty,
    countIf(is_excluded = 0 AND task_status = 'TODO') AS todo_qty,
    countIf(is_excluded = 0 AND task_status = 'DOING') AS doing_qty,
    countIf(is_excluded = 0 AND task_status = 'DONE') AS done_qty,
    
    -- 排除統計
    countIf(is_excluded = 1) AS excluded_qty,
    countIf(exclude_reason = 'bypass') AS bypass_qty,
    countIf(exclude_reason = 'E_prefix') AS e_prefix_qty,
    countIf(exclude_reason = 'C_prefix') AS c_prefix_qty,
    countIf(exclude_reason = 'Q_order') AS q_order_qty,
    countIf(exclude_reason = 'R_order') AS r_order_qty,
    
    -- 特殊規則統計
    countIf(is_special_v1_rule = 1) AS special_v1_rule_qty,
    
    now64(3) AS _mview_update_time

FROM silver.mv_fact_task_vx_attribution
GROUP BY 
    snapshot_date,
    vx_type,
    vx_subtype,
    plant,
    factory,
    line
"""
    
    client.query(create_sql)
    print("✅ 新 MView 已建立（包含 POPULATE）")
    
    time.sleep(3)
    
    # 步驟 3: 驗證 NPE 資料
    print("\n步驟 3: 驗證 NPE 資料已包含")
    print("-" * 80)
    
    result = client.query('''
    SELECT 
        vx_subtype,
        SUM(total_task_qty) as count
    FROM silver.mv_l5_metrics_realtime
    WHERE vx_type = 'V1'
    GROUP BY vx_subtype
    ORDER BY vx_subtype
    ''')
    
    print("V1 子類型分布:")
    for row in result.result_rows:
        subtype, count = row
        print(f"  • {subtype}: {count}")
    
    # 檢查是否有 V1_NPE
    has_npe = any(row[0] == 'V1_NPE' for row in result.result_rows)
    if has_npe:
        print("✅ V1_NPE 資料已包含")
    else:
        print("❌ V1_NPE 資料仍缺失")
    
    # 步驟 4: 重建 Gold MView
    print("\n步驟 4: 重建 Gold MView 以包含最新資料")
    print("-" * 80)
    
    # 刪除 Gold MView
    client.query("DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
    print("✅ Gold MView 已刪除")
    
    time.sleep(2)
    
    # 重建 Gold MView
    gold_sql = """
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
    
    client.query(gold_sql)
    print("✅ Gold MView 已重建")
    
    time.sleep(3)
    
    # 步驟 5: 驗證 Gold 層 NPE 資料
    print("\n步驟 5: 驗證 Gold 層 NPE 資料")
    print("-" * 80)
    
    result = client.query('''
    SELECT 
        vx_subtype,
        SUM(sum_total_task_qty) as count
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    WHERE vx_type = 'V1'
    GROUP BY vx_subtype
    ORDER BY vx_subtype
    ''')
    
    print("Gold 層 V1 子類型分布:")
    for row in result.result_rows:
        subtype, count = row
        print(f"  • {subtype}: {count}")
    
    # 檢查是否有 V1_NPE
    has_gold_npe = any(row[0] == 'V1_NPE' for row in result.result_rows)
    if has_gold_npe:
        print("✅ Gold 層 V1_NPE 資料已包含")
    else:
        print("❌ Gold 層 V1_NPE 資料仍缺失")
    
    print("\n" + "=" * 80)
    print("✅ 重建完成")
    print("=" * 80)
    print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
except Exception as e:
    print(f"\n❌ 錯誤: {str(e)}")
    import traceback
    traceback.print_exc()