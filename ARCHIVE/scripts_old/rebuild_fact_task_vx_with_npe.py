#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新建立 mv_fact_task_vx_attribution，應用 NPE 邏輯
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
print("重新建立 mv_fact_task_vx_attribution（應用 NPE 邏輯）")
print("=" * 80)
print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

try:
    # 步驟 1: 刪除舊 MView
    print("步驟 1: 刪除舊的 mv_fact_task_vx_attribution")
    print("-" * 80)
    
    sql = "DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution"
    client.query(sql)
    print("✅ 舊 MView 已刪除")
    
    time.sleep(2)
    
    # 步驟 2: 重新建立 MView（應用 NPE 邏輯）
    print("\n步驟 2: 重新建立 mv_fact_task_vx_attribution（應用 NPE 邏輯）")
    print("-" * 80)
    
    create_sql = """
CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (task_id)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    t.TaskId AS task_id,
    COALESCE(t.TaskCreateDate, toDate('1970-01-01')) AS task_create_date,
    t.TaskEndDate AS task_end_date,
    t.TaskCreateTime AS task_create_time,
    t.TaskClaimTime AS task_claim_time,
    t.TaskEndTime AS task_end_time,
    COALESCE(t.TaskStatus, 'Unknown') AS task_status,
    COALESCE(t.TaskBypass, 'N') AS task_bypass,
    t.TaskDefinitionKey AS task_definition_key,
    t.TaskName AS task_name,
    t.TaskAssigneeName AS task_assignee_name,
    t.TaskAssigneeAccount AS task_assignee_account,
    CASE 
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%'
        THEN 'V1'
        WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
        WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        ELSE COALESCE(substring(t.TaskDefinitionKey, 1, 2), 'Unknown')
    END AS vx_type,
    CASE 
        WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%')
             AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%')
        THEN 'V1_MFG'
        WHEN t.TaskDefinitionKey LIKE 'V1%' AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        WHEN t.TaskDefinitionKey LIKE 'V1%'
        THEN 'V1_MFG'
        ELSE NULL
    END AS vx_subtype,
    CASE 
        WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 1
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%'
        THEN 1
        ELSE 0
    END AS is_special_v1_rule,
    CASE 
        WHEN t.TaskBypass != 'N' THEN 1
        WHEN t.TaskDefinitionKey LIKE 'E%' OR t.TaskDefinitionKey LIKE 'C%' THEN 1
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'Q%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'R%' THEN 1
        ELSE 0
    END AS is_excluded,
    CASE 
        WHEN t.TaskBypass != 'N' THEN 'bypass'
        WHEN t.TaskDefinitionKey LIKE 'E%' THEN 'E_prefix'
        WHEN t.TaskDefinitionKey LIKE 'C%' THEN 'C_prefix'
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'Q%' THEN 'Q_order'
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'R%' THEN 'R_order'
        ELSE NULL
    END AS exclude_reason,
    t.Plant AS plant,
    t.Factory AS factory,
    t.Line AS line,
    t.ProcessInstanceId AS proc_inst_id,
    p.BUSINESS_KEY_ AS business_key,
    COALESCE(v.varinst_moNumber, t.MoNumber) AS mo_number,
    p.NAME_ AS proc_name,
    now64(3) AS _mview_update_time
FROM bronze.common_flowable_task_stats t
LEFT JOIN bronze.bpm_act_hi_procinst p 
    ON t.ProcessInstanceId = p.PROC_INST_ID_
LEFT JOIN silver.mv_varinst_pivoted v
    ON t.ProcessInstanceId = v.PROC_INST_ID_
WHERE t.TaskId IS NOT NULL 
  AND t.TaskId != ''
"""
    
    client.query(create_sql)
    print("✅ 新 MView 已建立（包含 POPULATE 和 NPE 邏輯）")
    
    time.sleep(3)
    
    # 步驟 3: 驗證 NPE 邏輯
    print("\n步驟 3: 驗證 NPE 邏輯已正確應用")
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
        print("❌ V1_NPE 仍為 0")
    
    time.sleep(2)
    
    # 步驟 4: 驗證 315% 規則
    print("\n步驟 4: 驗證 315% 規則")
    print("-" * 80)
    
    result = client.query('''
    SELECT 
        COUNT(*) as total_315_orders,
        COUNT(DISTINCT mo_number) as unique_mo_numbers
    FROM silver.mv_fact_task_vx_attribution
    WHERE mo_number LIKE '315%'
    ''')
    
    total, unique = result.result_rows[0]
    print(f"315% 工單總行數: {total}")
    print(f"315% 唯一工單號: {unique}")
    
    if total > 0:
        print(f"✅ 315% 規則已正確應用")
    
    print("\n" + "=" * 80)
    print("✅ 重新建立完成")
    print("=" * 80)
    print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
except Exception as e:
    print(f"\n❌ 錯誤: {str(e)}")
    import traceback
    traceback.print_exc()
