#!/usr/bin/env python3
"""
調試 V1 歸屬邏輯問題
檢查為什麼 ClickHouse 將非 V1 任務錯誤歸類為 V1
"""
import clickhouse_connect

def debug_v1_attribution():
    client = clickhouse_connect.get_client(
        host="REDACTED_IP",
        port=8121,
        username="default",
        password="default"
    )
    
    print("=" * 80)
    print("V1 歸屬邏輯調試")
    print("=" * 80)
    
    # 1. 檢查 Silver 層 2025-12-28 WJ2+NBU+E5 的所有任務
    print("\n1. Silver 層 2025-12-28 WJ2+NBU+E5 所有任務...")
    
    all_tasks_sql = """
    SELECT 
        task_id,
        vx_type,
        task_definition_key,
        mo_number,
        task_status,
        task_create_time
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_create_date = '2025-12-28'
      AND is_excluded = 0
    ORDER BY task_create_time
    """
    
    result = client.query(all_tasks_sql)
    if result.result_rows:
        print(f"  {'TaskId':<15} {'VX':<4} {'DefKey':<12} {'MoNumber':<12} {'Status':<8} {'CreateTime':<20}")
        print("  " + "-" * 85)
        
        v1_count = 0
        for row in result.result_rows:
            task_id, vx_type, def_key, mo_number, status, create_time = row
            if vx_type == 'V1':
                v1_count += 1
            print(f"  {task_id[:15]:<15} {vx_type:<4} {def_key:<12} {mo_number or 'NULL':<12} {status:<8} {str(create_time)[:19]}")
        
        print(f"\n  總任務: {len(result.result_rows)}, V1任務: {v1_count}")
    else:
        print("  ❌ 無任務資料")
    
    # 2. 檢查 V1 歸屬規則的具體應用
    print("\n2. V1 歸屬規則檢查...")
    
    v1_rule_sql = """
    SELECT 
        mo_number,
        task_definition_key,
        vx_type,
        COUNT(*) as task_count,
        CASE 
            WHEN mo_number LIKE '196%' OR mo_number LIKE '199%' OR mo_number LIKE '200%' 
              OR mo_number LIKE '210%' OR mo_number LIKE '212%' OR mo_number LIKE '213%' 
              OR mo_number LIKE '315%' THEN 'V1_by_mo'
            ELSE substring(task_definition_key, 1, 2)
        END as expected_vx
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_create_date = '2025-12-28'
      AND is_excluded = 0
    GROUP BY mo_number, task_definition_key, vx_type
    ORDER BY task_count DESC
    """
    
    result = client.query(v1_rule_sql)
    if result.result_rows:
        print(f"  {'MoNumber':<12} {'DefKey':<12} {'Current VX':<10} {'Expected VX':<12} {'Count':<6}")
        print("  " + "-" * 60)
        
        for row in result.result_rows:
            mo_number, def_key, current_vx, expected_vx, count = row
            mismatch = "❌" if current_vx != expected_vx else "✅"
            print(f"  {mo_number or 'NULL':<12} {def_key:<12} {current_vx:<10} {expected_vx:<12} {count:<6} {mismatch}")
    
    # 3. 檢查月度聚合的來源
    print("\n3. 月度聚合來源檢查...")
    
    monthly_source_sql = """
    SELECT 
        snapshot_date,
        COUNT(*) as records,
        SUM(CASE WHEN vx_type = 'V1' THEN done_qty ELSE 0 END) as v1_done_qty
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND time_period_type = 'month'
      AND time_period_value = '2025-12'
    GROUP BY snapshot_date
    ORDER BY snapshot_date DESC
    LIMIT 10
    """
    
    result = client.query(monthly_source_sql)
    if result.result_rows:
        print(f"  {'Snapshot Date':<15} {'Records':<8} {'V1 Done Qty':<12}")
        print("  " + "-" * 40)
        
        for row in result.result_rows:
            snapshot_date, records, v1_done_qty = row
            print(f"  {snapshot_date:<15} {records:<8} {v1_done_qty:<12}")
    
    # 4. 檢查 Bronze 層原始資料
    print("\n4. Bronze 層原始資料檢查...")
    
    bronze_sql = """
    SELECT 
        varinst_moNumber,
        TaskDefinitionKey,
        COUNT(*) as task_count
    FROM bronze.common_flowable_task_stats
    WHERE varinst_plant = 'WJ2' AND varinst_factory = 'NBU' AND varinst_lineName = 'E5'
      AND DATE(StartTime) = '2025-12-28'
      AND TaskBypass = 'N'
    GROUP BY varinst_moNumber, TaskDefinitionKey
    ORDER BY task_count DESC
    """
    
    result = client.query(bronze_sql)
    if result.result_rows:
        print(f"  {'MoNumber':<12} {'DefKey':<12} {'Count':<6}")
        print("  " + "-" * 35)
        
        for row in result.result_rows:
            mo_number, def_key, count = row
            print(f"  {mo_number or 'NULL':<12} {def_key:<12} {count:<6}")

def main():
    debug_v1_attribution()

if __name__ == "__main__":
    main()