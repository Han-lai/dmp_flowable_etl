#!/usr/bin/env python3
"""
重建 Silver 層 MVIEW 並驗證修正結果
"""

import clickhouse_connect
from datetime import datetime
import time

CLICKHOUSE_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def rebuild_mview():
    """重建 MVIEW"""
    print("\n" + "="*100)
    print("【開始】重建 Silver 層 MVIEW")
    print("="*100)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        # Step 1: 重建第一層 MVIEW
        print("\n【Step 1】重建第一層 MVIEW...")
        print("-" * 100)
        
        # 刪除並重建 mv_varinst_pivoted
        print("  - 重建 mv_varinst_pivoted...")
        client.command("DROP TABLE IF EXISTS silver.mv_varinst_pivoted")
        time.sleep(1)
        
        # 重建第一層 MVIEW（使用 sql/11_create_silver_mviews_layer1.sql 的邏輯）
        sql_layer1 = """
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
            now64(3) AS _mview_update_time
        FROM bronze.bpm_act_hi_varinst
        WHERE NAME_ IN ('moNumber', 'plant', 'factory', 'lineName', 'region')
        GROUP BY PROC_INST_ID_
        """
        
        client.command(sql_layer1)
        print("    ✅ mv_varinst_pivoted 重建完成")
        time.sleep(2)
        
        # Step 2: 重建第二層 MVIEW
        print("\n【Step 2】重建第二層 MVIEW...")
        print("-" * 100)
        
        print("  - 重建 mv_fact_task_vx_attribution...")
        client.command("DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution")
        time.sleep(1)
        
        # 重建 mv_fact_task_vx_attribution（使用修正後的邏輯）
        sql_layer2 = """
        CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution
        ENGINE = ReplacingMergeTree(_mview_update_time)
        ORDER BY (task_id)
        SETTINGS allow_nullable_key = 1
        POPULATE
        AS
        SELECT
            -- 主鍵
            t.TaskId AS task_id,
            
            -- 時間維度
            COALESCE(t.TaskCreateDate, toDate('1970-01-01')) AS task_create_date,
            t.TaskEndDate AS task_end_date,
            t.TaskCreateTime AS task_create_time,
            t.TaskClaimTime AS task_claim_time,
            t.TaskEndTime AS task_end_time,
            
            -- 任務屬性
            COALESCE(t.TaskStatus, 'Unknown') AS task_status,
            COALESCE(t.TaskBypass, 'N') AS task_bypass,
            t.TaskDefinitionKey AS task_definition_key,
            t.TaskName AS task_name,
            
            -- 人員資訊
            t.TaskAssigneeName AS task_assignee_name,
            t.TaskAssigneeAccount AS task_assignee_account,
            
            -- 預計算：Vx 歸屬（修正後的邏輯：工單號規則優先級最高）
            CASE 
                -- 優先級 1：工單號規則（最高，覆蓋所有 TaskDefinitionKey）
                WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
                WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
                THEN 'V1'
                
                -- 優先級 2：TaskDefinitionKey 前綴（當工單號規則不符合時）
                WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
                WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
                WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
                
                -- 預設值
                ELSE COALESCE(substring(t.TaskDefinitionKey, 1, 2), 'Unknown')
            END AS vx_type,
            
            -- 預計算：V1 子類型（修正後的邏輯：工單號規則優先）
            CASE 
                -- 工單號規則的 V1 任務（無論原始 TaskDefinitionKey 是什麼）
                WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037')
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%')
                     AND p.BUSINESS_KEY_ LIKE '%NPE%'
                THEN 'V1_NPE'
                
                WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037')
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
                      OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%')
                THEN 'V1_MFG'
                
                -- TaskDefinitionKey 的 V1 任務（工單號規則不符合時）
                WHEN t.TaskDefinitionKey LIKE 'V1%' AND p.BUSINESS_KEY_ LIKE '%NPE%'
                THEN 'V1_NPE'
                
                WHEN t.TaskDefinitionKey LIKE 'V1%'
                THEN 'V1_MFG'
                
                -- 其他情況（V2/V3 等）
                ELSE NULL
            END AS vx_subtype,
            
            -- 是否套用特殊 V1 規則（修正後的邏輯：工單號規則優先）
            CASE 
                WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 1
                -- 特定 315% 工單號
                WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037') THEN 1
                -- 其他工單號規則
                WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
                THEN 1
                ELSE 0
            END AS is_special_v1_rule,
            
            -- 排除標記
            CASE 
                WHEN t.TaskBypass != 'N' THEN 1
                WHEN t.TaskDefinitionKey LIKE 'E%' OR t.TaskDefinitionKey LIKE 'C%' THEN 1
                WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'Q%' 
                     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'R%' THEN 1
                ELSE 0
            END AS is_excluded,
            
            -- 排除原因
            CASE 
                WHEN t.TaskBypass != 'N' THEN 'bypass'
                WHEN t.TaskDefinitionKey LIKE 'E%' THEN 'E_prefix'
                WHEN t.TaskDefinitionKey LIKE 'C%' THEN 'C_prefix'
                WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'Q%' THEN 'Q_order'
                WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'R%' THEN 'R_order'
                ELSE NULL
            END AS exclude_reason,
            
            -- 維度
            t.Plant AS plant,
            t.Factory AS factory,
            t.Line AS line,
            
            -- 關聯欄位
            t.ProcessInstanceId AS proc_inst_id,
            p.BUSINESS_KEY_ AS business_key,
            COALESCE(v.varinst_moNumber, t.MoNumber) AS mo_number,
            p.NAME_ AS proc_name,
            
            -- Metadata
            now64(3) AS _mview_update_time

        FROM bronze.common_flowable_task_stats t
        LEFT JOIN bronze.bpm_act_hi_procinst p 
            ON t.ProcessInstanceId = p.PROC_INST_ID_
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.ProcessInstanceId = v.PROC_INST_ID_
        WHERE t.TaskId IS NOT NULL 
          AND t.TaskId != ''
        """
        
        client.command(sql_layer2)
        print("    ✅ mv_fact_task_vx_attribution 重建完成")
        time.sleep(2)
        
        print("\n【完成】MVIEW 重建完成")
        print("="*100)
        
        # 驗證修正結果
        print("\n【驗證】檢查修正結果...")
        print("-" * 100)
        
        # 查詢 V1_NPE 任務
        sql_verify = """
        SELECT 
            vx_type,
            vx_subtype,
            task_status,
            COUNT(*) AS task_count
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE vx_type = 'V1'
          AND vx_subtype = 'V1_NPE'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND toDate(task_create_time) = '2025-12-31'
          AND is_excluded = 0
        GROUP BY vx_type, vx_subtype, task_status
        ORDER BY task_status
        """
        
        result = client.query(sql_verify)
        rows = result.result_rows
        
        todo_count = 0
        doing_count = 0
        done_count = 0
        
        for vx_type, vx_subtype, task_status, task_count in rows:
            print(f"  {vx_type} / {vx_subtype} / {task_status}: {task_count} 筆")
            if task_status == 'TODO':
                todo_count = task_count
            elif task_status == 'DOING':
                doing_count = task_count
            elif task_status == 'DONE':
                done_count = task_count
        
        total = todo_count + doing_count + done_count
        
        print("\n【驗證結果】")
        print("-" * 100)
        print(f"TODO:  {todo_count} 筆 (預期: 9) {'✅' if todo_count == 9 else '❌'}")
        print(f"DOING: {doing_count} 筆 (預期: 2) {'✅' if doing_count == 2 else '❌'}")
        print(f"DONE:  {done_count} 筆 (預期: 1) {'✅' if done_count == 1 else '❌'}")
        print(f"小計:  {total} 筆 (預期: 12) {'✅' if total == 12 else '❌'}")
        
        if total == 12 and todo_count == 9 and doing_count == 2 and done_count == 1:
            print("\n✅ 修正成功！所有數據符合預期")
        else:
            print("\n❌ 修正未完全成功，數據仍不符合預期")
        
        print("\n" + "="*100)
        
    except Exception as e:
        print(f"\n❌ 重建失敗：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    rebuild_mview()
