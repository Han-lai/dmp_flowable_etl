#!/usr/bin/env python3
"""
診斷為什麼沒有 V1_NPE 任務
"""

import clickhouse_connect
from datetime import datetime

CLICKHOUSE_CONFIG = {
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def diagnose():
    """診斷"""
    print("\n" + "="*100)
    print("【診斷】V1_NPE 任務缺失原因")
    print("="*100)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        # 檢查 WJ2+NBU+E5+2025-12-31 的所有任務
        print("\n【檢查 1】WJ2+NBU+E5+2025-12-31 的所有任務")
        print("-" * 100)
        
        sql = """
        SELECT 
            t.TaskDefinitionKey,
            COALESCE(v.varinst_moNumber, t.MoNumber) AS mo_number,
            p.BUSINESS_KEY_,
            COUNT(*) AS task_count
        FROM bronze.common_flowable_task_stats t
        LEFT JOIN bronze.bpm_act_hi_procinst p 
            ON t.ProcessInstanceId = p.PROC_INST_ID_
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.ProcessInstanceId = v.PROC_INST_ID_
        WHERE t.Plant = 'WJ2' 
          AND t.Factory = 'NBU' 
          AND t.Line = 'E5'
          AND toDate(t.TaskCreateDate) = '2025-12-31'
          AND t.TaskId IS NOT NULL 
          AND t.TaskId != ''
        GROUP BY t.TaskDefinitionKey, mo_number, p.BUSINESS_KEY_
        ORDER BY t.TaskDefinitionKey
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        print(f"{'TaskDefinitionKey':<20} {'MoNumber':<20} {'BusinessKey':<30} {'Count':<10}")
        print("-" * 100)
        
        for task_def_key, mo_number, business_key, task_count in rows:
            print(f"{str(task_def_key):<20} {str(mo_number):<20} {str(business_key):<30} {task_count:<10}")
        
        # 檢查是否有符合工單號規則的任務
        print("\n【檢查 2】是否有符合工單號規則（196/199/200/210/212/213/315）的任務")
        print("-" * 100)
        
        sql_mo = """
        SELECT 
            COALESCE(v.varinst_moNumber, t.MoNumber) AS mo_number,
            COUNT(*) AS task_count
        FROM bronze.common_flowable_task_stats t
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.ProcessInstanceId = v.PROC_INST_ID_
        WHERE t.Plant = 'WJ2' 
          AND t.Factory = 'NBU' 
          AND t.Line = 'E5'
          AND toDate(t.TaskCreateDate) = '2025-12-31'
          AND t.TaskId IS NOT NULL 
          AND t.TaskId != ''
          AND (COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
               OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
               OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
               OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
               OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
               OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
               OR COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037'))
        GROUP BY mo_number
        ORDER BY mo_number
        """
        
        result = client.query(sql_mo)
        rows = result.result_rows
        
        if len(rows) == 0:
            print("❌ 沒有符合工單號規則的任務")
        else:
            print(f"✅ 找到 {len(rows)} 個符合工單號規則的工單號：")
            for mo_number, task_count in rows:
                print(f"  {mo_number}: {task_count} 筆")
        
        # 檢查 business_key 是否包含 NPE
        print("\n【檢查 3】business_key 是否包含 'NPE'")
        print("-" * 100)
        
        sql_npe = """
        SELECT 
            CASE WHEN p.BUSINESS_KEY_ LIKE '%NPE%' THEN 'NPE' ELSE 'Non-NPE' END AS npe_flag,
            COUNT(*) AS task_count
        FROM bronze.common_flowable_task_stats t
        LEFT JOIN bronze.bpm_act_hi_procinst p 
            ON t.ProcessInstanceId = p.PROC_INST_ID_
        WHERE t.Plant = 'WJ2' 
          AND t.Factory = 'NBU' 
          AND t.Line = 'E5'
          AND toDate(t.TaskCreateDate) = '2025-12-31'
          AND t.TaskId IS NOT NULL 
          AND t.TaskId != ''
        GROUP BY npe_flag
        """
        
        result = client.query(sql_npe)
        rows = result.result_rows
        
        for npe_flag, task_count in rows:
            print(f"  {npe_flag}: {task_count} 筆")
        
        # 檢查 TaskDefinitionKey 是否以 V1 開頭
        print("\n【檢查 4】TaskDefinitionKey 是否以 V1 開頭")
        print("-" * 100)
        
        sql_v1 = """
        SELECT 
            CASE WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1' ELSE 'Non-V1' END AS v1_flag,
            COUNT(*) AS task_count
        FROM bronze.common_flowable_task_stats t
        WHERE t.Plant = 'WJ2' 
          AND t.Factory = 'NBU' 
          AND t.Line = 'E5'
          AND toDate(t.TaskCreateDate) = '2025-12-31'
          AND t.TaskId IS NOT NULL 
          AND t.TaskId != ''
        GROUP BY v1_flag
        """
        
        result = client.query(sql_v1)
        rows = result.result_rows
        
        for v1_flag, task_count in rows:
            print(f"  {v1_flag}: {task_count} 筆")
        
        print("\n" + "="*100)
        
    except Exception as e:
        print(f"\n❌ 診斷失敗：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    diagnose()
