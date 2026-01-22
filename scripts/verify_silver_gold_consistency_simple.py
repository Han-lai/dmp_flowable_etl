#!/usr/bin/env python3
"""
簡化版本：驗證 Silver 和 Gold 層的資料一致性
測試條件: WJ2+NBU+E5 2025-12-30
"""

import clickhouse_connect

def main():
    print("=== Silver vs Gold 一致性驗證 ===")
    print("測試條件: WJ2+NBU+E5 2025-12-30")
    
    # 連接 ClickHouse
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    # 1. 查詢 Silver 層 Fact 表原始資料
    print("\n1. 查詢 Silver 層 Fact 表原始資料...")
    
    fact_query = """
    SELECT 
        task_definition_key,
        task_assignee_name,
        task_status,
        vx_type,
        vx_subtype,
        is_excluded,
        exclude_reason,
        mo_number
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE toDate(task_create_time) = '2025-12-30'
      AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    ORDER BY task_definition_key, task_create_time
    """
    
    try:
        fact_results = client.query(fact_query).result_rows
        print(f"  Silver Fact 表原始資料: {len(fact_results)} 筆")
        
        # 統計原始資料
        raw_status_count = {}
        excluded_count = 0
        included_status_count = {}
        
        print("  原始資料詳情:")
        print("  任務定義 | 指派人 | 狀態 | Vx | 子類型 | 排除 | 排除原因 | 工單號")
        print("  " + "-" * 100)
        
        for row in fact_results:
            task_def_key, assignee, task_status, vx_type, vx_subtype, is_excluded, exclude_reason, mo_number = row
            
            # 原始統計
            if task_status not in raw_status_count:
                raw_status_count[task_status] = 0
            raw_status_count[task_status] += 1
            
            # 排除統計
            if is_excluded:
                excluded_count += 1
            else:
                if task_status not in included_status_count:
                    included_status_count[task_status] = 0
                included_status_count[task_status] += 1
            
            assignee_display = (assignee or 'NULL')[:10]
            excluded_display = '是' if is_excluded else '否'
            excluded_reason_display = (exclude_reason or '')[:10]
            print(f"  {task_def_key:12} | {assignee_display:10} | {task_status:5} | {vx_type:2} | {vx_subtype or '':6} | {excluded_display:2} | {excluded_reason_display:10} | {mo_number or 'NULL'}")
        
        print(f"\n  原始狀態統計:")
        for status, count in raw_status_count.items():
            print(f"    {status}: {count}")
        
        print(f"\n  未排除狀態統計:")
        for status, count in included_status_count.items():
            print(f"    {status}: {count}")
        print(f"    排除: {excluded_count}")
        
    except Exception as e:
        print(f"  ❌ Silver Fact 表查詢錯誤: {e}")
        return
    
    # 2. 查詢 Silver 層 Metrics
    print("\n2. 查詢 Silver 層 Metrics...")
    
    metrics_query = """
    SELECT 
        snapshot_date,
        vx_type,
        vx_subtype,
        plant,
        factory,
        line,
        todo_qty,
        doing_qty,
        done_qty,
        total_task_qty,
        excluded_qty
    FROM silver.mv_l5_metrics_realtime FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND snapshot_date = '2025-12-30'
    ORDER BY vx_type, vx_subtype
    """
    
    try:
        metrics_results = client.query(metrics_query).result_rows
        print(f"  Silver Metrics 資料: {len(metrics_results)} 筆")
        
        silver_totals = {'TODO': 0, 'DOING': 0, 'DONE': 0, 'TOTAL': 0, 'EXCLUDED': 0}
        
        print("  Metrics 詳情:")
        print("  日期 | Vx | 子類型 | 廠區 | TODO | DOING | DONE | 總計 | 排除")
        print("  " + "-" * 70)
        
        for row in metrics_results:
            snapshot_date, vx_type, vx_subtype, plant, factory, line, todo_qty, doing_qty, done_qty, total_task_qty, excluded_qty = row
            
            print(f"  {snapshot_date} | {vx_type:2} | {vx_subtype or '':6} | {plant}-{factory}-{line} | {todo_qty:4} | {doing_qty:5} | {done_qty:4} | {total_task_qty:4} | {excluded_qty:4}")
            
            silver_totals['TODO'] += todo_qty
            silver_totals['DOING'] += doing_qty
            silver_totals['DONE'] += done_qty
            silver_totals['TOTAL'] += total_task_qty
            silver_totals['EXCLUDED'] += excluded_qty
        
        print(f"\n  Silver Metrics 總計:")
        for key, value in silver_totals.items():
            print(f"    {key}: {value}")
        
    except Exception as e:
        print(f"  ❌ Silver Metrics 查詢錯誤: {e}")
        return
    
    # 3. 查詢 Gold 層資料
    print("\n3. 查詢 Gold 層資料...")
    
    gold_query = """
    SELECT 
        snapshot_date,
        vx_type,
        vx_subtype,
        plant,
        factory,
        line,
        sum_todo_qty,
        sum_doing_qty,
        sum_done_qty,
        sum_total_task_qty,
        sum_excluded_qty,
        completion_rate,
        progress_rate
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND snapshot_date = '2025-12-30'
    ORDER BY vx_type, vx_subtype
    """
    
    try:
        gold_results = client.query(gold_query).result_rows
        print(f"  Gold 層資料: {len(gold_results)} 筆")
        
        gold_totals = {'TODO': 0, 'DOING': 0, 'DONE': 0, 'TOTAL': 0, 'EXCLUDED': 0}
        
        print("  Gold 詳情:")
        print("  日期 | Vx | 子類型 | 廠區 | TODO | DOING | DONE | 總計 | 排除 | 完成率%")
        print("  " + "-" * 80)
        
        for row in gold_results:
            snapshot_date, vx_type, vx_subtype, plant, factory, line, todo_qty, doing_qty, done_qty, total_task_qty, excluded_qty, completion_rate, progress_rate = row
            
            print(f"  {snapshot_date} | {vx_type:2} | {vx_subtype or '':6} | {plant}-{factory}-{line} | {todo_qty:4} | {doing_qty:5} | {done_qty:4} | {total_task_qty:4} | {excluded_qty:4} | {completion_rate:7.1f}")
            
            gold_totals['TODO'] += todo_qty
            gold_totals['DOING'] += doing_qty
            gold_totals['DONE'] += done_qty
            gold_totals['TOTAL'] += total_task_qty
            gold_totals['EXCLUDED'] += excluded_qty
        
        print(f"\n  Gold 總計:")
        for key, value in gold_totals.items():
            print(f"    {key}: {value}")
        
    except Exception as e:
        print(f"  ❌ Gold 層查詢錯誤: {e}")
        return
    
    # 4. 一致性比較
    print("\n=== 一致性比較 ===")
    
    print("\n📊 各層數據對比:")
    print("層級           | TODO | DOING | DONE | 總計 | 排除")
    print("-" * 50)
    print(f"Silver Fact    | {included_status_count.get('TODO', 0):4} | {included_status_count.get('DOING', 0):5} | {included_status_count.get('DONE', 0):4} | {sum(included_status_count.values()):4} | {excluded_count:4}")
    print(f"Silver Metrics | {silver_totals['TODO']:4} | {silver_totals['DOING']:5} | {silver_totals['DONE']:4} | {silver_totals['TOTAL']:4} | {silver_totals['EXCLUDED']:4}")
    print(f"Gold           | {gold_totals['TODO']:4} | {gold_totals['DOING']:5} | {gold_totals['DONE']:4} | {gold_totals['TOTAL']:4} | {gold_totals['EXCLUDED']:4}")
    
    # 檢查一致性
    print("\n🔍 一致性檢查:")
    
    # Silver Fact vs Silver Metrics
    fact_total = sum(included_status_count.values())
    if (included_status_count.get('TODO', 0) == silver_totals['TODO'] and
        included_status_count.get('DOING', 0) == silver_totals['DOING'] and
        included_status_count.get('DONE', 0) == silver_totals['DONE'] and
        excluded_count == silver_totals['EXCLUDED']):
        print("✅ Silver Fact ↔ Silver Metrics: 完全一致")
    else:
        print("❌ Silver Fact ↔ Silver Metrics: 不一致")
        print(f"   TODO: Fact {included_status_count.get('TODO', 0)} vs Metrics {silver_totals['TODO']}")
        print(f"   DOING: Fact {included_status_count.get('DOING', 0)} vs Metrics {silver_totals['DOING']}")
        print(f"   DONE: Fact {included_status_count.get('DONE', 0)} vs Metrics {silver_totals['DONE']}")
        print(f"   排除: Fact {excluded_count} vs Metrics {silver_totals['EXCLUDED']}")
    
    # Silver Metrics vs Gold
    if silver_totals == gold_totals:
        print("✅ Silver Metrics ↔ Gold: 完全一致")
    else:
        print("❌ Silver Metrics ↔ Gold: 不一致")
        for key in ['TODO', 'DOING', 'DONE', 'TOTAL', 'EXCLUDED']:
            if silver_totals[key] != gold_totals[key]:
                print(f"   {key}: Silver {silver_totals[key]} vs Gold {gold_totals[key]}")
    
    print("\n=== 總結 ===")
    print(f"✅ 找到 WJ2+NBU+E5 2025-12-30 的資料")
    print(f"   原始任務數: {len(fact_results)}")
    print(f"   未排除任務數: {fact_total}")
    print(f"   排除任務數: {excluded_count}")
    print(f"   Silver → Gold 資料流: {'正常' if silver_totals == gold_totals else '異常'}")

if __name__ == '__main__':
    main()