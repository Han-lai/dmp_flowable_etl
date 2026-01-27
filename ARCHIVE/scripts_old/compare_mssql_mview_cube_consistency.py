#!/usr/bin/env python3
"""
比較 MSSQL、MView 和 Cube 的資料一致性
測試條件: WJ2+NBU+E5 2025-12-30
"""

import clickhouse_connect
import pyodbc
from datetime import datetime

def connect_mssql():
    """連接 MSSQL"""
    connection_string = (
        "DRIVER={SQL Server};"
        "SERVER=REDACTED_IP,1433;"
        "DATABASE=flowable;"
        "UID=sa;"
        "PWD=Aa123456;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(connection_string)

def connect_clickhouse():
    """連接 ClickHouse"""
    return clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )

def query_mssql_source(mssql_conn):
    """查詢 MSSQL 原始資料"""
    print("\n1. 查詢 MSSQL 原始資料...")
    
    # 查詢原始任務資料
    mssql_query = """
    SELECT 
        t.TASK_DEF_KEY_,
        t.ASSIGNEE_,
        t.CREATE_TIME_,
        CAST(t.CREATE_TIME_ AS DATE) as create_date,
        CASE 
            WHEN t.END_TIME_ IS NOT NULL THEN 'DONE'
            WHEN t.ASSIGNEE_ IS NOT NULL THEN 'DOING' 
            ELSE 'TODO'
        END as task_status,
        v.TEXT_ as work_order,
        -- 判斷 Plant/Factory/Line
        CASE 
            WHEN v.TEXT_ LIKE 'WJ2%' THEN 'WJ2'
            ELSE 'OTHER'
        END as plant,
        CASE 
            WHEN v.TEXT_ LIKE '%NBU%' THEN 'NBU'
            WHEN v.TEXT_ LIKE '%NPE%' THEN 'NPE'
            WHEN v.TEXT_ LIKE '%SMT%' THEN 'SMT'
            ELSE 'OTHER'
        END as factory,
        CASE 
            WHEN v.TEXT_ LIKE '%E5%' THEN 'E5'
            WHEN v.TEXT_ LIKE '%E1%' THEN 'E1'
            WHEN v.TEXT_ LIKE '%E2%' THEN 'E2'
            ELSE 'OTHER'
        END as line,
        -- 判斷 Vx 類型
        CASE 
            WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
            WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
            WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
            ELSE 'OTHER'
        END as vx_type
    FROM ACT_HI_TASKINST t
    LEFT JOIN ACT_HI_VARINST v ON t.PROC_INST_ID_ = v.PROC_INST_ID_ 
                               AND v.NAME_ = 'workOrder'
    WHERE CAST(t.CREATE_TIME_ AS DATE) = '2025-12-30'
      AND v.TEXT_ LIKE 'WJ2%NBU%E5%'
    ORDER BY t.TASK_DEF_KEY_, t.CREATE_TIME_
    """
    
    cursor = mssql_conn.cursor()
    cursor.execute(mssql_query)
    results = cursor.fetchall()
    
    print(f"  MSSQL 原始資料: {len(results)} 筆")
    
    # 統計任務狀態
    status_count = {}
    vx_status_count = {}
    
    for row in results:
        task_def_key, assignee, create_time, create_date, task_status, work_order, plant, factory, line, vx_type = row
        
        # 總計統計
        if task_status not in status_count:
            status_count[task_status] = 0
        status_count[task_status] += 1
        
        # 按 Vx 類型統計
        vx_key = f"{vx_type}"
        if vx_key not in vx_status_count:
            vx_status_count[vx_key] = {'TODO': 0, 'DOING': 0, 'DONE': 0}
        vx_status_count[vx_key][task_status] += 1
        
        print(f"    {task_def_key} | {assignee or 'NULL':15} | {task_status:5} | {work_order} | {vx_type}")
    
    print(f"\n  MSSQL 狀態統計:")
    for status, count in status_count.items():
        print(f"    {status}: {count}")
    
    print(f"\n  MSSQL 按 Vx 類型統計:")
    for vx_type, counts in vx_status_count.items():
        total = sum(counts.values())
        print(f"    {vx_type}: 總計 {total} (TODO: {counts['TODO']}, DOING: {counts['DOING']}, DONE: {counts['DONE']})")
    
    return status_count, vx_status_count

def query_bronze_layer(ch_conn):
    """查詢 Bronze 層資料"""
    print("\n2. 查詢 Bronze 層資料...")
    
    bronze_query = """
    SELECT 
        task_def_key,
        assignee,
        create_time,
        toDate(create_time) as create_date,
        CASE 
            WHEN end_time IS NOT NULL THEN 'DONE'
            WHEN assignee IS NOT NULL AND assignee != '' THEN 'DOING' 
            ELSE 'TODO'
        END as task_status,
        work_order,
        -- 解析 Plant/Factory/Line
        CASE 
            WHEN work_order LIKE 'WJ2%' THEN 'WJ2'
            ELSE 'OTHER'
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
        -- 判斷 Vx 類型
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
        print(f"  Bronze 層資料: {len(results)} 筆")
        
        # 統計任務狀態
        status_count = {}
        vx_status_count = {}
        
        for row in results:
            task_def_key, assignee, create_time, create_date, task_status, work_order, plant, factory, line, vx_type = row
            
            # 總計統計
            if task_status not in status_count:
                status_count[task_status] = 0
            status_count[task_status] += 1
            
            # 按 Vx 類型統計
            vx_key = f"{vx_type}"
            if vx_key not in vx_status_count:
                vx_status_count[vx_key] = {'TODO': 0, 'DOING': 0, 'DONE': 0}
            vx_status_count[vx_key][task_status] += 1
            
            print(f"    {task_def_key} | {assignee or 'NULL':15} | {task_status:5} | {work_order} | {vx_type}")
        
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

def query_silver_layer(ch_conn):
    """查詢 Silver 層資料"""
    print("\n3. 查詢 Silver 層資料...")
    
    silver_query = """
    SELECT 
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
        results = ch_conn.query(silver_query).result_rows
        print(f"  Silver 層資料: {len(results)} 筆")
        
        total_counts = {'TODO': 0, 'DOING': 0, 'DONE': 0, 'TOTAL': 0, 'EXCLUDED': 0}
        vx_status_count = {}
        
        for row in results:
            vx_type, vx_subtype, plant, factory, line, todo_qty, doing_qty, done_qty, total_task_qty, excluded_qty = row
            
            print(f"    {vx_type} | {vx_subtype:6} | {plant}-{factory}-{line} | TODO: {todo_qty}, DOING: {doing_qty}, DONE: {done_qty}, 總計: {total_task_qty}, 排除: {excluded_qty}")
            
            # 累計統計
            total_counts['TODO'] += todo_qty
            total_counts['DOING'] += doing_qty
            total_counts['DONE'] += done_qty
            total_counts['TOTAL'] += total_task_qty
            total_counts['EXCLUDED'] += excluded_qty
            
            # 按 Vx 類型統計
            vx_key = f"{vx_type}"
            if vx_key not in vx_status_count:
                vx_status_count[vx_key] = {'TODO': 0, 'DOING': 0, 'DONE': 0}
            vx_status_count[vx_key]['TODO'] += todo_qty
            vx_status_count[vx_key]['DOING'] += doing_qty
            vx_status_count[vx_key]['DONE'] += done_qty
        
        print(f"\n  Silver 狀態統計:")
        print(f"    TODO: {total_counts['TODO']}")
        print(f"    DOING: {total_counts['DOING']}")
        print(f"    DONE: {total_counts['DONE']}")
        print(f"    總計: {total_counts['TOTAL']}")
        print(f"    排除: {total_counts['EXCLUDED']}")
        
        print(f"\n  Silver 按 Vx 類型統計:")
        for vx_type, counts in vx_status_count.items():
            total = sum(counts.values())
            print(f"    {vx_type}: 總計 {total} (TODO: {counts['TODO']}, DOING: {counts['DOING']}, DONE: {counts['DONE']})")
        
        return total_counts, vx_status_count
        
    except Exception as e:
        print(f"  ❌ Silver 層查詢錯誤: {e}")
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
        
        total_counts = {'TODO': 0, 'DOING': 0, 'DONE': 0, 'TOTAL': 0, 'EXCLUDED': 0}
        vx_status_count = {}
        
        for row in results:
            snapshot_date, vx_type, vx_subtype, plant, factory, line, todo_qty, doing_qty, done_qty, total_task_qty, excluded_qty, completion_rate, progress_rate = row
            
            print(f"    {snapshot_date} | {vx_type} | {vx_subtype:6} | {plant}-{factory}-{line} | TODO: {todo_qty}, DOING: {doing_qty}, DONE: {done_qty}, 總計: {total_task_qty}, 排除: {excluded_qty} | 完成率: {completion_rate:.1f}%")
            
            # 累計統計
            total_counts['TODO'] += todo_qty
            total_counts['DOING'] += doing_qty
            total_counts['DONE'] += done_qty
            total_counts['TOTAL'] += total_task_qty
            total_counts['EXCLUDED'] += excluded_qty
            
            # 按 Vx 類型統計
            vx_key = f"{vx_type}"
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

def compare_results(mssql_status, bronze_status, silver_status, gold_status):
    """比較各層資料一致性"""
    print("\n=== 資料一致性比較 ===")
    
    print("\n📊 總計比較:")
    print("層級     | TODO | DOING | DONE | 總計")
    print("-" * 40)
    
    # MSSQL
    mssql_total = sum(mssql_status.values()) if mssql_status else 0
    mssql_todo = mssql_status.get('TODO', 0)
    mssql_doing = mssql_status.get('DOING', 0)
    mssql_done = mssql_status.get('DONE', 0)
    print(f"MSSQL    | {mssql_todo:4} | {mssql_doing:5} | {mssql_done:4} | {mssql_total:4}")
    
    # Bronze
    bronze_total = sum(bronze_status.values()) if bronze_status else 0
    bronze_todo = bronze_status.get('TODO', 0)
    bronze_doing = bronze_status.get('DOING', 0)
    bronze_done = bronze_status.get('DONE', 0)
    print(f"Bronze   | {bronze_todo:4} | {bronze_doing:5} | {bronze_done:4} | {bronze_total:4}")
    
    # Silver
    silver_todo = silver_status.get('TODO', 0)
    silver_doing = silver_status.get('DOING', 0)
    silver_done = silver_status.get('DONE', 0)
    silver_total = silver_status.get('TOTAL', 0)
    print(f"Silver   | {silver_todo:4} | {silver_doing:5} | {silver_done:4} | {silver_total:4}")
    
    # Gold
    gold_todo = gold_status.get('TODO', 0)
    gold_doing = gold_status.get('DOING', 0)
    gold_done = gold_status.get('DONE', 0)
    gold_total = gold_status.get('TOTAL', 0)
    print(f"Gold     | {gold_todo:4} | {gold_doing:5} | {gold_done:4} | {gold_total:4}")
    
    # 一致性檢查
    print("\n🔍 一致性檢查:")
    
    # 檢查 MSSQL vs Bronze
    if mssql_status and bronze_status:
        if mssql_status == bronze_status:
            print("✅ MSSQL ↔ Bronze: 一致")
        else:
            print("❌ MSSQL ↔ Bronze: 不一致")
            for status in ['TODO', 'DOING', 'DONE']:
                mssql_count = mssql_status.get(status, 0)
                bronze_count = bronze_status.get(status, 0)
                if mssql_count != bronze_count:
                    print(f"   {status}: MSSQL {mssql_count} vs Bronze {bronze_count}")
    
    # 檢查 Silver vs Gold
    silver_comparable = {'TODO': silver_todo, 'DOING': silver_doing, 'DONE': silver_done}
    gold_comparable = {'TODO': gold_todo, 'DOING': gold_doing, 'DONE': gold_done}
    
    if silver_comparable == gold_comparable:
        print("✅ Silver ↔ Gold: 一致")
    else:
        print("❌ Silver ↔ Gold: 不一致")
        for status in ['TODO', 'DOING', 'DONE']:
            silver_count = silver_comparable[status]
            gold_count = gold_comparable[status]
            if silver_count != gold_count:
                print(f"   {status}: Silver {silver_count} vs Gold {gold_count}")
    
    # 檢查端到端一致性
    if mssql_total == silver_total == gold_total:
        print("✅ 端到端一致性: 通過")
    else:
        print("❌ 端到端一致性: 失敗")
        print(f"   MSSQL: {mssql_total}, Silver: {silver_total}, Gold: {gold_total}")

def main():
    print("=== MSSQL vs MView vs Cube 一致性驗證 ===")
    print("測試條件: WJ2+NBU+E5 2025-12-30")
    
    try:
        # 連接資料庫
        mssql_conn = connect_mssql()
        ch_conn = connect_clickhouse()
        
        # 查詢各層資料
        mssql_status, mssql_vx_status = query_mssql_source(mssql_conn)
        bronze_status, bronze_vx_status = query_bronze_layer(ch_conn)
        silver_status, silver_vx_status = query_silver_layer(ch_conn)
        gold_status, gold_vx_status = query_gold_layer(ch_conn)
        
        # 比較結果
        compare_results(mssql_status, bronze_status, silver_status, gold_status)
        
        # 關閉連接
        mssql_conn.close()
        
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")

if __name__ == '__main__':
    main()