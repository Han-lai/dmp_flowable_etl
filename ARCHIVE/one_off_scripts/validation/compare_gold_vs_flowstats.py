#!/usr/bin/env python3
"""
比對 Gold 層 L5 任務數 vs FlowableTaskStats (bronze 層)

篩選條件：
- Plant = 'WJ2'
- Factory = 'NBU'  
- Line = 'E5'
- 日期 = 2025-12-25
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("=" * 80)
    print("Gold 層 vs FlowableTaskStats (Bronze 層) L5 任務數比對")
    print("條件: CNE WJ2 NBU E5 | 日期: 2025-12-25")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 查詢參數
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-12-25'
    
    # ========================================
    # 1. Bronze 層 (FlowableTaskStats) 查詢
    # ========================================
    print("\n" + "=" * 80)
    print("📊 1. Bronze 層 (common_flowable_task_stats) - FlowableTaskStats 來源")
    print("=" * 80)
    
    # 時間範圍條件 (與 L5_task_sample.sql 一致)
    time_filter = f"""
        (
            toDate(TaskCreateTime) = '{target_date}'
            OR toDate(TaskClaimTime) = '{target_date}'
            OR toDate(TaskEndTime) = '{target_date}'
        )
    """
    
    bronze_filter = f"""
        Plant = '{plant}'
        AND Factory = '{factory}'
        AND Line = '{line}'
        AND {time_filter}
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    """
    
    # Bronze 總數
    bronze_total_sql = f"""
        SELECT count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {bronze_filter}
    """
    bronze_total = client.command(bronze_total_sql)
    print(f"\n   Total Task (不含 bypass): {bronze_total:,}")
    
    # Bronze 按狀態分布
    bronze_status_sql = f"""
        SELECT 
            TaskStatus,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {bronze_filter}
        GROUP BY TaskStatus
        ORDER BY cnt DESC
    """
    result = client.query(bronze_status_sql)
    
    bronze_done = 0
    bronze_doing = 0
    bronze_todo = 0
    
    print("   TaskStatus 分布:")
    for row in result.result_rows:
        status = row[0]
        cnt = row[1]
        print(f"      {status}: {cnt:,}")
        if status.upper() == 'DONE':
            bronze_done = cnt
        elif status.upper() == 'DOING':
            bronze_doing = cnt
        elif status.upper() == 'TODO':
            bronze_todo = cnt
    
    # Bronze 按 Vx 分布
    bronze_vx_sql = f"""
        SELECT 
            substring(TaskDefinitionKey, 1, 2) as vx_type,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {bronze_filter}
        GROUP BY vx_type
        ORDER BY cnt DESC
    """
    result = client.query(bronze_vx_sql)
    print("\n   Vx 分布:")
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]:,}")
    
    # ========================================
    # 2. Gold 層查詢
    # ========================================
    print("\n" + "=" * 80)
    print("📊 2. Gold 層 (rmv_l5_task_completion) - 自動聚合 MView")
    print("=" * 80)
    
    # Gold 層使用 snapshot_date (task_create_date) 作為日期
    # 注意: Gold 層沒有 region 條件，只有 plant, factory, line
    gold_sql = f"""
        SELECT 
            vx_type,
            sum(total_task) as total_task,
            sum(todo_count) as todo_count,
            sum(doing_count) as doing_count,
            sum(done_count) as done_count
        FROM gold.rmv_l5_task_completion FINAL
        WHERE snapshot_date = '{target_date}'
          AND plant = '{plant}'
          AND factory = '{factory}'
          AND line = '{line}'
        GROUP BY vx_type
        ORDER BY total_task DESC
    """
    
    try:
        result = client.query(gold_sql)
        
        gold_total = 0
        gold_done = 0
        gold_doing = 0
        gold_todo = 0
        
        print("\n   按 Vx 類型彙總:")
        for row in result.result_rows:
            vx = row[0]
            total = row[1]
            todo = row[2]
            doing = row[3]
            done = row[4]
            print(f"      [{vx}] Total={total}, TODO={todo}, DOING={doing}, DONE={done}")
            gold_total += total
            gold_todo += todo
            gold_doing += doing
            gold_done += done
        
        print(f"\n   總計:")
        print(f"      Total Task: {gold_total:,}")
        print(f"      TODO: {gold_todo:,}")
        print(f"      DOING: {gold_doing:,}")
        print(f"      DONE: {gold_done:,}")
        
    except Exception as e:
        print(f"   ❌ 查詢錯誤: {e}")
        gold_total = 0
        gold_done = 0
        gold_doing = 0
        gold_todo = 0
    
    # ========================================
    # 3. 差異比對
    # ========================================
    print("\n" + "=" * 80)
    print("📊 3. 差異比對結果")
    print("=" * 80)
    
    print("\n   | 指標 | Bronze (FlowableTaskStats) | Gold (rmv_l5_task_completion) | 差異 |")
    print("   |------|---------------------------|------------------------------|------|")
    print(f"   | Total | {bronze_total:,} | {gold_total:,} | {bronze_total - gold_total:+,} |")
    print(f"   | TODO | {bronze_todo:,} | {gold_todo:,} | {bronze_todo - gold_todo:+,} |")
    print(f"   | DOING | {bronze_doing:,} | {gold_doing:,} | {bronze_doing - gold_doing:+,} |")
    print(f"   | DONE | {bronze_done:,} | {gold_done:,} | {bronze_done - gold_done:+,} |")
    
    # 判斷是否一致
    total_match = bronze_total == gold_total
    todo_match = bronze_todo == gold_todo
    doing_match = bronze_doing == gold_doing
    done_match = bronze_done == gold_done
    
    all_match = total_match and todo_match and doing_match and done_match
    
    print("\n" + "=" * 80)
    if all_match:
        print("✅ 結論: Gold 層與 Bronze 層 (FlowableTaskStats) 數據完全一致！")
    else:
        print("⚠️ 結論: Gold 層與 Bronze 層 (FlowableTaskStats) 數據存在差異")
        print("\n   可能原因:")
        print("   1. Gold 層使用 task_create_date 篩選，而 Bronze 層使用 OR 時間條件")
        print("   2. Gold 層使用 Silver 層 (BPM 原生表) 計算，而非 FlowableTaskStats")
        print("   3. is_excluded 過濾條件可能不同於 TaskBypass")
        print("   4. 資料刷新時間差異")
    
    # ========================================
    # 4. 追加: 檢查 Silver 層原始資料
    # ========================================
    print("\n" + "=" * 80)
    print("📊 4. Silver 層 (mv_fact_task_vx) - 追查資料來源")
    print("=" * 80)
    
    silver_sql = f"""
        SELECT 
            vx_type,
            task_status,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_create_date = '{target_date}'
          AND plant = '{plant}'
          AND factory = '{factory}'
          AND line = '{line}'
          AND is_excluded = 0
        GROUP BY vx_type, task_status
        ORDER BY vx_type, task_status
    """
    
    try:
        result = client.query(silver_sql)
        silver_total = 0
        current_vx = None
        vx_subtotal = 0
        
        for row in result.result_rows:
            vx = row[0]
            status = row[1]
            cnt = row[2]
            
            if vx != current_vx:
                if current_vx is not None:
                    print(f"      小計: {vx_subtotal}")
                print(f"   [{vx}]")
                current_vx = vx
                vx_subtotal = 0
            
            print(f"      {status}: {cnt:,}")
            silver_total += cnt
            vx_subtotal += cnt
        
        if current_vx is not None:
            print(f"      小計: {vx_subtotal}")
        
        print(f"\n   Silver 層總計: {silver_total:,}")
        
        # 與 Gold 比較
        if silver_total == gold_total:
            print("   ✅ Silver 與 Gold 一致")
        else:
            print(f"   ⚠️ Silver ({silver_total}) 與 Gold ({gold_total}) 不一致，差異: {silver_total - gold_total}")
            
    except Exception as e:
        print(f"   ❌ 查詢錯誤: {e}")
    
    print("\n" + "=" * 80)
    client.close()

if __name__ == "__main__":
    main()
