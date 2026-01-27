#!/usr/bin/env python3
"""
比較 Bronze、Silver、Gold 層的資料一致性
測試條件: WJ2+NBU+E5 2025-12-30
"""

import clickhouse_connect
from datetime import datetime

def connect_clickhouse():
    """連接 ClickHouse"""
    return clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )

def query_bronze_layer(ch_conn):
    """查詢 Bronze 層原始資料"""
    print("\n1. 查詢 Bronze 層原始資料...")
    
    # 先檢查 Bronze 層表結構
    tables_query = """
    SELECT name, engine, total_rows
    FROM system.tables
    WHERE database = 'bronze' 
      AND name LIKE '%taskinst%'
    ORDER BY name
    """
    
    tables = ch_conn.query(tables_query).result_rows
    print("  Bronze 層表:")
    for table in tables:
        print(f"    {table[0]}: {table[1]}, {table[2]:,} 行")
    
    # 查詢任務資料
    bronze_query = """
    SELECT 
        task_def_key,
        assignee,
        create_time,
        end_time,
        toDate(create_time) as create_date,
        CASE 
            WHEN end_time IS NOT NULL THEN 'DONE'
            WHEN assignee IS NOT NULL AND assignee != '' THEN 'DOING' 
            ELSE 'TODO'
        END as task_status,
        work_order,
        -- 解析維度
        CASE 
            WHEN work_order LIKE 'WJ2%' THEN 'WJ2'
            ELSE extractAll(work_order, '[A-Z]{2,3}')[1]
        END as plant,
        CASE 
            WHEN work_order LIKE '%NBU%' THEN 'NBU'
            WHEN work_order LIKE '%NPE%' THEN 'NPE'
            WHEN work_order LIKE '%SMT%' THEN 'SMT'
            ELSE 'OTHER'
        END as factory,
        CASE 
            WHEN work_order LIKE '%E5%' THEN 'E5'
            WHEN work_order LIKE '%E1%' THEN 'E1'
            WHEN work_order LIKE '%E2%' THEN 'E2'
            ELSE 'OTHER'
        END as line,
        CASE 
            WHEN task_def_key LIKE 'V1%' THEN 'V1'
            WHEN task_def_key LIKE 'V2%' THEN 'V2'
            WHEN task_def_key LIKE 'V3%' THEN 'V3'
            ELSE 'OTHER'
        END as vx_type
    FROM bronze.bpm_act_hi_taskinst FINAL
    WHERE toDate(create_time) = '2025-12-30'
      AND work_order LIKE 'WJ2%NBU%E5%'
    ORDER BY task_def_key, create_time
    """
    
    try:
        results = ch_conn.query(bronze_query).result_rows
        print(f"\n  Bronze 層資料: {len(results)} 筆")
        
        if len(results) == 0:
            print("  ❌ 沒有找到 Bronze 層資料")
            return {}, {}
        
        # 統計任務狀態
        status_count = {}
        vx_status_count = {}
        
        print("  詳細資料:")
        print("  任務定義 | 指派人 | 狀態 | 工單號 | Vx類型")
        print("  " + "-" * 80)
        
        for row in results:
            task_def_key, assignee, create_time, end_time, create_date, task_status, work_order, plant, factory, line, vx_type = row
            
            # 總計統計
            if task_status not in status_count:
                status_count[task_status] = 0
            status_count[task_status] += 1
            
            # 按 Vx 類型統計
            if vx_type not in vx_status_count:
                vx_status_count[vx_type] = {'TODO': 0, 'DOING': 0, 'DONE': 0}
            vx_status_count[vx_type][task_status] += 1
            
            assignee_display = (assignee or 'NULL')[:15]
            print(f"  {task_def_key:12} | {assignee_display:15} | {task_status:5} | {work_order} | {vx_type}")
        
        print(f"\n  Bronze 狀態統計:")
        for status, count in status_count.items():
            print(f"    {status}: {count}")
        
        print(f"\n  Bronze 按 Vx 類型統計:")
        for vx_type, counts in vx_status_count.items():
            total = sum(counts.values())
            print(f"    {vx_type}: 總計 {total} (TODO: {counts['TODO']}, DOING: {counts['DOING']}, DONE: {counts['DONE']})")
        
        return status_count, vx_status_count
        
    except Exception as e:
        print(f"  ❌ Bronze 層查詢錯誤: {e}")
        return {}, {}

def query_silver_fact_table(ch_conn):
    """查詢 Silver 層 Fact 表"""
    print("\n2. 查詢 Silver 層 Fact 表...")
    
    fact_query = """
    SELECT 
        task_definition_key,
        task_assignee_name,
        task_create_time,
        task_end_time,
        task_status,
        work_order,
        plant,
        factory,
        line,
        vx_type,
        vx_subtype,
        is_excluded,
        excluded_reason
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE toDate(task_create_time) = '2025-12-30'
      AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    ORDER BY task_definition_key, task_create_time
    """
    
    try:
        results = ch_conn.query(fact_query).result_rows
        print(f"  Silver Fact 表資料: {len(results)} 筆")
        
        if len(results) == 0:
            print("  ❌ 沒有找到 Silver Fact 表資料")
            return {}, {}
        
        # 統計任務狀態
        status_count = {}
        vx_status_count = {}
        excluded_count = 0
        
        print("  詳細資料:")
        print("  任務定義 | 指派人 | 狀態 | Vx類型 | 子類型 | 排除 | 排除原因")
        print("  " + "-" * 90)
        
        for row in results:
            task_def_key, assignee, create_time, end_time, task_status, work_order, plant, factory, line, vx_type, vx_subtype, is_excluded, excluded_reason = row
            
            if is_excluded:
                excluded_count += 1
                continue
            
            # 總計統計 (只計算未排除的)
            if task_status not in status_count:
                status_count[task_status] = 0
            status_count[task_status] += 1
            
            # 按 Vx 類型統計
            vx_key = f"{vx_type}_{vx_subtype}" if vx_subtype else vx_type
            if vx_key not in vx_status_count:
                vx_status_count[vx_key] = {'TODO': 0, 'DOING': 0, 'DONE': 0}
            vx_status_count[vx_key][task_status] += 1
            
            assignee_display = (assignee or 'NULL')[:10]
            excluded_display = '是' if is_excluded else '否'
            excluded_reason_display = (excluded_reason or '')[:10]
            print(f"  {task_def_key:12} | {assignee_display:10} | {task_status:5} | {vx_type:2} | {vx_subtype or '':6} | {excluded_display:2} | {excluded_reason_display}")
        
        print(f"\n  Silver Fact 狀態統計 (未排除):")
        for status, count in status_count.items():
            print(f"    {status}: {count}")
        print(f"    排除: {excluded_count}")
        
        print(f"\n  Silver Fact 按 Vx 類型統計:")
        for vx_type, counts in vx_status_count.items():
            total = sum(counts.values())
            print(f"    {vx_type}: 總計 {total} (TODO: {counts['TODO']}, DOING: {counts['DOING']}, DONE: {counts['DONE']})")
        
        return status_count, vx_status_count
        
    except Exception as e:
        print(f"  ❌ Silver Fact 表查詢錯誤: {e}")
        return {}, {}

def query_silver_metrics(ch_conn):
    """查詢 Silver 層 Metrics"""
    print("\n3. 查詢 Silver 層 Metrics...")
    
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
        results = ch_conn.query(metrics_query).result_rows
        print(f"  Silver Metrics 資料: {len(results)} 筆")
        
        if len(results) == 0:
            print("  ❌ 沒有找到 Silver Metrics 資料")
            return {}, {}
        
        total_counts = {'TODO': 0, 'DOING': 0, 'DONE': 0, 'TOTAL': 0, 'EXCLUDED': 0}
        vx_status_count = {}
        
        print("  詳細資料:")
        print("  日期 | Vx | 子類型 | 廠區 | TODO | DOING | DONE | 總計 | 排除")
        print("  " + "-" * 70)
        
        for row in results:
            snapshot_date, vx_type, vx_subtype, plant, factory, line, todo_qty, doing_qty, done_qty, total_task_qty, excluded_qty = row
            
            print(f"  {snapshot_date} | {vx_type:2} | {vx_subtype or '':6} | {plant}-{factory}-{line} | {todo_qty:4} | {doing_qty:5} | {done_qty:4} | {total_task_qty:4} | {excluded_qty:4}")
            
            # 累計統計
            total_counts['TODO'] += todo_qty
            total_counts['DOING'] += doing_qty
            total_counts['DONE'] += done_qty
            total_counts['TOTAL'] += total_task_qty
            total_counts['EXCLUDED'] += excluded_qty
            
            # 按 Vx 類型統計
            vx_key = f"{vx_type}_{vx_subtype}" if vx_subtype else vx_type
            if vx_key not in vx_status_count:
                vx_status_count[vx_key] = {'TODO': 0, 'DOING': 0, 'DONE': 0}
            vx_status_count[vx_key]['TODO'] += todo_qty
            vx_status_count[vx_key]['DOING'] += doing_qty
            vx_status_count[vx_key]['DONE'] += done_qty
        
        print(f"\n  Silver Metrics 狀態統計:")
        print(f"    TODO: {total_counts['TODO']}")
        print(f"    DOING: {total_counts['DOING']}")
        print(f"    DONE: {total_counts['DONE']}")
        print(f"    總計: {total_counts['TOTAL']}")
        print(f"    排除: {total_counts['EXCLUDED']}")
        
        print(f"\n  Silver Metrics 按 Vx 類型統計:")
        for vx_type, counts in vx_status_count.items():
            total = sum(counts.values())
            print(f"    {vx_type}: 總計 {total} (TODO: {counts['TODO']}, DOING: {counts['DOING']}, DONE: {counts['DONE']})")
        
        return total_counts, vx_status_count
        
    except Exception as e:
        print(f"  ❌ Silver Metrics 查詢錯誤: {e}")
        return {}, {}

def query_gold_layer(ch_conn):
    """查詢 Gold 層資料"""
    print("\n4. 查詢 Gold 層資料...")
    
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
        results = ch_conn.query(gold_query).result_rows
        print(f"  Gold 層資料: {len(results)} 筆")
        
        if len(results) == 0:
            print("  ❌ 沒有找到 Gold 層資料")
            return {}, {}
        
        total_counts = {'TODO': 0, 'DOING': 0, 'DONE': 0, 'TOTAL': 0, 'EXCLUDED': 0}
        vx_status_count = {}
        
        print("  詳細資料:")
        print("  日期 | Vx | 子類型 | 廠區 | TODO | DOING | DONE | 總計 | 排除 | 完成率%")
        print("  " + "-" * 80)
        
        for row in results:
            snapshot_date, vx_type, vx_subtype, plant, factory, line, todo_qty, doing_qty, done_qty, total_task_qty, excluded_qty, completion_rate, progress_rate = row
            
            print(f"  {snapshot_date} | {vx_type:2} | {vx_subtype or '':6} | {plant}-{factory}-{line} | {todo_qty:4} | {doing_qty:5} | {done_qty:4} | {total_task_qty:4} | {excluded_qty:4} | {completion_rate:7.1f}")
            
            # 累計統計
            total_counts['TODO'] += todo_qty
            total_counts['DOING'] += doing_qty
            total_counts['DONE'] += done_qty
            total_counts['TOTAL'] += total_task_qty
            total_counts['EXCLUDED'] += excluded_qty
            
            # 按 Vx 類型統計
            vx_key = f"{vx_type}_{vx_subtype}" if vx_subtype else vx_type
            if vx_key not in vx_status_count:
                vx_status_count[vx_key] = {'TODO': 0, 'DOING': 0, 'DONE': 0}
            vx_status_count[vx_key]['TODO'] += todo_qty
            vx_status_count[vx_key]['DOING'] += doing_qty
            vx_status_count[vx_key]['DONE'] += done_qty
        
        print(f"\n  Gold 狀態統計:")
        print(f"    TODO: {total_counts['TODO']}")
        print(f"    DOING: {total_counts['DOING']}")
        print(f"    DONE: {total_counts['DONE']}")
        print(f"    總計: {total_counts['TOTAL']}")
        print(f"    排除: {total_counts['EXCLUDED']}")
        
        print(f"\n  Gold 按 Vx 類型統計:")
        for vx_type, counts in vx_status_count.items():
            total = sum(counts.values())
            print(f"    {vx_type}: 總計 {total} (TODO: {counts['TODO']}, DOING: {counts['DOING']}, DONE: {counts['DONE']})")
        
        return total_counts, vx_status_count
        
    except Exception as e:
        print(f"  ❌ Gold 層查詢錯誤: {e}")
        return {}, {}

def compare_results(bronze_status, silver_fact_status, silver_metrics_status, gold_status):
    """比較各層資料一致性"""
    print("\n=== 資料一致性比較 ===")
    
    print("\n📊 總計比較:")
    print("層級           | TODO | DOING | DONE | 總計 | 排除")
    print("-" * 50)
    
    # Bronze
    bronze_total = sum(bronze_status.values()) if bronze_status else 0
    bronze_todo = bronze_status.get('TODO', 0)
    bronze_doing = bronze_status.get('DOING', 0)
    bronze_done = bronze_status.get('DONE', 0)
    print(f"Bronze         | {bronze_todo:4} | {bronze_doing:5} | {bronze_done:4} | {bronze_total:4} | N/A")
    
    # Silver Fact
    fact_total = sum(silver_fact_status.values()) if silver_fact_status else 0
    fact_todo = silver_fact_status.get('TODO', 0)
    fact_doing = silver_fact_status.get('DOING', 0)
    fact_done = silver_fact_status.get('DONE', 0)
    print(f"Silver Fact    | {fact_todo:4} | {fact_doing:5} | {fact_done:4} | {fact_total:4} | N/A")
    
    # Silver Metrics
    metrics_todo = silver_metrics_status.get('TODO', 0)
    metrics_doing = silver_metrics_status.get('DOING', 0)
    metrics_done = silver_metrics_status.get('DONE', 0)
    metrics_total = silver_metrics_status.get('TOTAL', 0)
    metrics_excluded = silver_metrics_status.get('EXCLUDED', 0)
    print(f"Silver Metrics | {metrics_todo:4} | {metrics_doing:5} | {metrics_done:4} | {metrics_total:4} | {metrics_excluded:4}")
    
    # Gold
    gold_todo = gold_status.get('TODO', 0)
    gold_doing = gold_status.get('DOING', 0)
    gold_done = gold_status.get('DONE', 0)
    gold_total = gold_status.get('TOTAL', 0)
    gold_excluded = gold_status.get('EXCLUDED', 0)
    print(f"Gold           | {gold_todo:4} | {gold_doing:5} | {gold_done:4} | {gold_total:4} | {gold_excluded:4}")
    
    # 一致性檢查
    print("\n🔍 一致性檢查:")
    
    # 檢查 Silver Metrics vs Gold
    silver_comparable = {'TODO': metrics_todo, 'DOING': metrics_doing, 'DONE': metrics_done, 'TOTAL': metrics_total, 'EXCLUDED': metrics_excluded}
    gold_comparable = {'TODO': gold_todo, 'DOING': gold_doing, 'DONE': gold_done, 'TOTAL': gold_total, 'EXCLUDED': gold_excluded}
    
    if silver_comparable == gold_comparable:
        print("✅ Silver Metrics ↔ Gold: 完全一致")
    else:
        print("❌ Silver Metrics ↔ Gold: 不一致")
        for status in ['TODO', 'DOING', 'DONE', 'TOTAL', 'EXCLUDED']:
            silver_count = silver_comparable[status]
            gold_count = gold_comparable[status]
            if silver_count != gold_count:
                print(f"   {status}: Silver {silver_count} vs Gold {gold_count}")
    
    # 檢查 Bronze vs Silver 的總數
    if bronze_total > 0 and metrics_total > 0:
        if bronze_total == metrics_total:
            print("✅ Bronze ↔ Silver 總數: 一致")
        else:
            print(f"❌ Bronze ↔ Silver 總數: 不一致 (Bronze {bronze_total} vs Silver {metrics_total})")
    
    # 檢查資料流完整性
    print("\n📈 資料流完整性:")
    if bronze_total > 0:
        print(f"  Bronze → Silver 轉換率: {metrics_total}/{bronze_total} = {metrics_total/bronze_total*100:.1f}%")
    if metrics_total > 0:
        print(f"  Silver → Gold 轉換率: {gold_total}/{metrics_total} = {gold_total/metrics_total*100:.1f}%")

def main():
    print("=== Bronze vs Silver vs Gold 一致性驗證 ===")
    print("測試條件: WJ2+NBU+E5 2025-12-30")
    
    try:
        # 連接 ClickHouse
        ch_conn = connect_clickhouse()
        
        # 查詢各層資料
        bronze_status, bronze_vx_status = query_bronze_layer(ch_conn)
        silver_fact_status, silver_fact_vx_status = query_silver_fact_table(ch_conn)
        silver_metrics_status, silver_metrics_vx_status = query_silver_metrics(ch_conn)
        gold_status, gold_vx_status = query_gold_layer(ch_conn)
        
        # 比較結果
        compare_results(bronze_status, silver_fact_status, silver_metrics_status, gold_status)
        
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")

if __name__ == '__main__':
    main()