#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新建立 mv_varinst_pivoted，包含 NPE 變數
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
print("重新建立 mv_varinst_pivoted")
print("=" * 80)
print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

try:
    # 步驟 1: 刪除舊 MView
    print("步驟 1: 刪除舊的 mv_varinst_pivoted")
    print("-" * 80)
    
    sql = "DROP TABLE IF EXISTS silver.mv_varinst_pivoted"
    client.query(sql)
    print("✅ 舊 MView 已刪除")
    
    time.sleep(2)
    
    # 步驟 2: 重新建立 MView（不過濾 NAME_）
    print("\n步驟 2: 重新建立 mv_varinst_pivoted（包含所有變數名稱）")
    print("-" * 80)
    
    create_sql = """
CREATE MATERIALIZED VIEW silver.mv_varinst_pivoted
ENGINE = ReplacingMergeTree()
ORDER BY (PROC_INST_ID_)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT 
    PROC_INST_ID_,
    MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber,
    MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS varinst_plant,
    MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS varinst_factory,
    MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS varinst_lineName,
    MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS varinst_region,
    arrayStringConcat(arrayDistinct(groupArray(NAME_)), ',') AS varinst_name,
    now64(3) AS _mview_update_time
FROM bronze.bpm_act_hi_varinst
GROUP BY PROC_INST_ID_
"""
    
    client.query(create_sql)
    print("✅ 新 MView 已建立（包含 POPULATE）")
    
    time.sleep(3)
    
    # 步驟 3: 驗證資料
    print("\n步驟 3: 驗證 NPE 資料已填充")
    print("-" * 80)
    
    result = client.query('''
    SELECT 
        COUNT(*) as total_rows,
        COUNT(CASE WHEN varinst_name LIKE '%NPE%' THEN 1 END) as npe_count
    FROM silver.mv_varinst_pivoted
    ''')
    
    total, npe = result.result_rows[0]
    print(f"總行數: {total}")
    print(f"NPE 行數: {npe}")
    
    if npe > 0:
        print(f"✅ NPE 資料已填充 ({npe} 筆)")
    else:
        print("❌ NPE 資料仍為 0")
    
    time.sleep(2)
    
    # 步驟 4: 驗證 mv_fact_task_vx_attribution 中的 NPE 邏輯
    print("\n步驟 4: 驗證 mv_fact_task_vx_attribution 中的 NPE 邏輯")
    print("-" * 80)
    
    result = client.query('''
    SELECT 
        COUNT(*) as total_rows,
        COUNT(CASE WHEN vx_subtype = 'V1_NPE' THEN 1 END) as v1_npe_count,
        COUNT(CASE WHEN vx_subtype = 'V1_MFG' THEN 1 END) as v1_mfg_count
    FROM silver.mv_fact_task_vx_attribution
    ''')
    
    total, npe, mfg = result.result_rows[0]
    print(f"總行數: {total}")
    print(f"V1_NPE: {npe}")
    print(f"V1_MFG: {mfg}")
    
    if npe > 0:
        print(f"✅ V1_NPE 邏輯已正確應用 ({npe} 筆)")
    else:
        print("⚠️ V1_NPE 仍為 0（可能需要重新建立 mv_fact_task_vx_attribution）")
    
    print("\n" + "=" * 80)
    print("✅ 重新建立完成")
    print("=" * 80)
    print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
except Exception as e:
    print(f"\n❌ 錯誤: {str(e)}")
    import traceback
    traceback.print_exc()
