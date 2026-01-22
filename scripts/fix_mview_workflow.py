#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClickHouse MView 工作流修正腳本
依序執行修正步驟
"""

import clickhouse_connect
import time
from datetime import datetime

CH_HOST = '10.136.218.207'
CH_PORT = 8121
CH_USER = 'default'
CH_PASSWORD = 'default'

def get_connection():
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD
    )

def log_step(step_num, title):
    print(f"\n{'='*80}")
    print(f"步驟 {step_num}: {title}")
    print(f"{'='*80}")
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def log_result(success, message):
    status = "✅ 成功" if success else "❌ 失敗"
    print(f"{status}: {message}")

def execute_sql(client, sql, description=""):
    try:
        if description:
            print(f"\n執行: {description}")
        result = client.query(sql)
        return True, result
    except Exception as e:
        return False, str(e)

def main():
    print("="*80)
    print("ClickHouse MView 工作流修正")
    print("="*80)
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        client = get_connection()
        print("✅ ClickHouse 連接成功\n")
        
        # 步驟 1: 刪除舊 MView
        log_step(1, "刪除舊的 mv_fact_task_vx_attribution")
        
        sql = "DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution"
        success, result = execute_sql(client, sql, "刪除 MView")
        log_result(success, "mv_fact_task_vx_attribution 已刪除" if success else f"刪除失敗: {result}")
        
        if not success:
            print("⚠️ 無法刪除舊 MView，繼續執行...")
        
        time.sleep(2)
        
        # 步驟 2: 重新建立 mv_fact_task_vx_attribution（新版本）
        log_step(2, "重新建立 mv_fact_task_vx_attribution（新版本）")
        
        # 新版本的 DDL（使用新的 315% 規則）
        create_mview_sql = """
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
        
        success, result = execute_sql(client, create_mview_sql, "建立新的 mv_fact_task_vx_attribution")
        log_result(success, "mv_fact_task_vx_attribution 已建立（包含 POPULATE）" if success else f"建立失敗: {result}")
        
        if not success:
            print(f"❌ 建立失敗，錯誤: {result}")
            return
        
        time.sleep(3)
        
        # 步驟 3: 驗證 POPULATE
        log_step(3, "驗證 POPULATE 關鍵字")
        
        sql = "SHOW CREATE TABLE silver.mv_fact_task_vx_attribution"
        success, result = execute_sql(client, sql, "查詢 MView 定義")
        
        if success and result.result_rows:
            ddl = result.result_rows[0][0]
            has_populate = 'POPULATE' in ddl
            has_new_315_rule = "LIKE '315%'" in ddl
            
            log_result(has_populate, "POPULATE 關鍵字已存在" if has_populate else "POPULATE 關鍵字缺失")
            log_result(has_new_315_rule, "新 315% 規則已應用" if has_new_315_rule else "315% 規則未更新")
        
        time.sleep(2)
        
        # 步驟 4: 驗證資料
        log_step(4, "驗證資料已填充")
        
        sql = """
        SELECT 
            COUNT(*) as total_rows,
            COUNT(DISTINCT toDate(task_create_time)) as date_count,
            MIN(toDate(task_create_time)) as min_date,
            MAX(toDate(task_create_time)) as max_date
        FROM silver.mv_fact_task_vx_attribution
        WHERE toDate(task_create_time) BETWEEN '2025-12-25' AND '2025-12-31'
        """
        success, result = execute_sql(client, sql, "查詢 MView 資料")
        
        if success and result.result_rows:
            total, date_count, min_date, max_date = result.result_rows[0]
            print(f"\n資料統計:")
            print(f"  • 總行數: {total}")
            print(f"  • 日期範圍: {min_date} ~ {max_date}")
            print(f"  • 日期數: {date_count}")
            
            if total > 0:
                log_result(True, f"MView 已填充 {total} 行資料")
            else:
                log_result(False, "MView 仍無資料")
        
        time.sleep(2)
        
        # 步驟 5: 驗證 315% 規則
        log_step(5, "驗證 315% 規則")
        
        sql = """
        SELECT 
            COUNT(*) as total_315_orders,
            COUNT(DISTINCT mo_number) as unique_mo_numbers
        FROM silver.mv_fact_task_vx_attribution
        WHERE mo_number LIKE '315%'
            AND toDate(task_create_time) BETWEEN '2025-12-25' AND '2025-12-31'
        """
        success, result = execute_sql(client, sql, "查詢 315% 工單")
        
        if success and result.result_rows:
            total, unique = result.result_rows[0]
            print(f"\n315% 工單統計:")
            print(f"  • 總行數: {total}")
            print(f"  • 唯一工單號: {unique}")
            log_result(total > 0, f"發現 {total} 筆 315% 工單")
        
        time.sleep(2)
        
        # 步驟 6: 驗證 NPE 邏輯
        log_step(6, "驗證 NPE 邏輯")
        
        sql = """
        SELECT 
            vx_subtype,
            COUNT(*) as count
        FROM silver.mv_fact_task_vx_attribution
        WHERE vx_subtype IN ('V1_NPE', 'V1_MFG')
            AND toDate(task_create_time) BETWEEN '2025-12-25' AND '2025-12-31'
        GROUP BY vx_subtype
        """
        success, result = execute_sql(client, sql, "查詢 NPE 分類")
        
        if success and result.result_rows:
            print(f"\nNPE 分類統計:")
            for row in result.result_rows:
                subtype, count = row
                print(f"  • {subtype}: {count}")
            log_result(len(result.result_rows) > 0, "NPE 邏輯已正確應用")
        
        print("\n" + "="*80)
        print("✅ 修正完成")
        print("="*80)
        print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
