#!/usr/bin/env python3
"""
修正 V1 歸屬邏輯問題
工單號 315% 的規則與 TaskDefinitionKey V3 衝突時，應該以 TaskDefinitionKey 為準
"""
import clickhouse_connect

def analyze_v1_attribution_issue():
    client = clickhouse_connect.get_client(
        host="REDACTED_IP",
        port=8121,
        username="default",
        password="default"
    )
    
    print("=" * 80)
    print("V1 歸屬邏輯問題分析與修正建議")
    print("=" * 80)
    
    # 1. 分析問題：315% 工單號但 V3 TaskDefinitionKey 的衝突
    print("\n1. 問題分析：315% 工單號 vs V3 TaskDefinitionKey 衝突...")
    
    conflict_sql = """
    SELECT 
        mo_number,
        task_definition_key,
        vx_type,
        COUNT(*) as task_count,
        COUNT(DISTINCT task_create_date) as date_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE mo_number LIKE '315%'
      AND task_definition_key LIKE 'V3%'
      AND vx_type = 'V1'
    GROUP BY mo_number, task_definition_key, vx_type
    ORDER BY task_count DESC
    LIMIT 20
    """
    
    result = client.query(conflict_sql)
    if result.result_rows:
        print(f"  發現 {len(result.result_rows)} 組衝突的歸屬規則:")
        print(f"  {'MoNumber':<12} {'DefKey':<15} {'VX':<4} {'Tasks':<6} {'Days':<5}")
        print("  " + "-" * 50)
        
        total_affected = 0
        for row in result.result_rows:
            mo_number, def_key, vx_type, task_count, date_count = row
            total_affected += task_count
            print(f"  {mo_number:<12} {def_key:<15} {vx_type:<4} {task_count:<6} {date_count:<5}")
        
        print(f"\n  總計受影響任務: {total_affected:,} 筆")
    else:
        print("  ✅ 未發現衝突")
    
    # 2. 檢查正確的歸屬邏輯應該是什麼
    print("\n2. 正確歸屬邏輯建議...")
    
    print("  目前邏輯 (有問題):")
    print("  CASE")
    print("    WHEN mo_number LIKE '315%' THEN 'V1'  -- 優先級太高")
    print("    ELSE substring(task_definition_key, 1, 2)")
    print("  END")
    
    print("\n  建議修正邏輯:")
    print("  CASE")
    print("    WHEN task_definition_key LIKE 'V3%' THEN 'V3'  -- TaskDefinitionKey 優先")
    print("    WHEN mo_number LIKE '196%|199%|200%|210%|212%|213%|315%' THEN 'V1'")
    print("    ELSE substring(task_definition_key, 1, 2)")
    print("  END")
    
    # 3. 計算修正後的影響
    print("\n3. 修正後影響評估...")
    
    impact_sql = """
    SELECT 
        plant,
        factory,
        line,
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE mo_number LIKE '315%'
      AND task_definition_key LIKE 'V3%'
      AND vx_type = 'V1'
    GROUP BY plant, factory, line
    ORDER BY total_tasks DESC
    """
    
    result = client.query(impact_sql)
    if result.result_rows:
        print(f"  受影響的產線:")
        print(f"  {'Plant':<6} {'Factory':<8} {'Line':<8} {'Total':<8} {'Done':<8}")
        print("  " + "-" * 50)
        
        total_tasks = 0
        total_done = 0
        for row in result.result_rows:
            plant, factory, line, tasks, done = row
            total_tasks += tasks
            total_done += done
            print(f"  {plant:<6} {factory:<8} {line:<8} {tasks:<8} {done:<8}")
        
        print(f"\n  總計: {total_tasks:,} 筆任務, {total_done:,} 筆完成")
    
    # 4. 檢查 WJ2+NBU+E5 的具體影響
    print("\n4. WJ2+NBU+E5 具體影響...")
    
    wj2_impact_sql = """
    SELECT 
        task_create_date,
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND mo_number LIKE '315%'
      AND task_definition_key LIKE 'V3%'
      AND vx_type = 'V1'
    GROUP BY task_create_date
    ORDER BY task_create_date DESC
    LIMIT 10
    """
    
    result = client.query(wj2_impact_sql)
    if result.result_rows:
        print(f"  WJ2+NBU+E5 受影響日期:")
        print(f"  {'Date':<12} {'Total':<8} {'Done':<8}")
        print("  " + "-" * 30)
        
        for row in result.result_rows:
            date, total, done = row
            print(f"  {date:<12} {total:<8} {done:<8}")
    else:
        print("  ✅ WJ2+NBU+E5 無受影響任務")

def generate_fix_sql():
    """生成修正 SQL"""
    print("\n" + "=" * 80)
    print("修正 SQL 生成")
    print("=" * 80)
    
    print("\n需要修正的 Silver 層 Materialized View:")
    print("檔案位置: sync/silver_mviews.py")
    
    print("\n修正前的 vx_type 邏輯:")
    print("""
    CASE 
        WHEN varinst_moNumber LIKE '196%' OR varinst_moNumber LIKE '199%' OR varinst_moNumber LIKE '200%' 
          OR varinst_moNumber LIKE '210%' OR varinst_moNumber LIKE '212%' OR varinst_moNumber LIKE '213%' 
          OR varinst_moNumber LIKE '315%' THEN 'V1'
        ELSE substring(TaskDefinitionKey, 1, 2)
    END as vx_type
    """)
    
    print("\n修正後的 vx_type 邏輯:")
    print("""
    CASE 
        WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'  
        WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        WHEN TaskDefinitionKey LIKE 'V4%' THEN 'V4'
        WHEN TaskDefinitionKey LIKE 'V5%' THEN 'V5'
        WHEN varinst_moNumber LIKE '196%' OR varinst_moNumber LIKE '199%' OR varinst_moNumber LIKE '200%' 
          OR varinst_moNumber LIKE '210%' OR varinst_moNumber LIKE '212%' OR varinst_moNumber LIKE '213%' 
          OR varinst_moNumber LIKE '315%' THEN 'V1'
        ELSE substring(TaskDefinitionKey, 1, 2)
    END as vx_type
    """)
    
    print("\n修正步驟:")
    print("1. 修改 sync/silver_mviews.py 中的 vx_type 邏輯")
    print("2. 重新建立 Silver 層 Materialized View")
    print("3. 重新生成 Gold 層快照")
    print("4. 驗證修正結果")

def main():
    analyze_v1_attribution_issue()
    generate_fix_sql()

if __name__ == "__main__":
    main()