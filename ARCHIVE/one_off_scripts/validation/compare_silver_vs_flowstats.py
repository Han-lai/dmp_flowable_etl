#!/usr/bin/env python3
"""
比對 Silver 層 vs Bronze 層 (FlowableTaskStats) L5 任務數

使用相同的 OR 時間邏輯:
- task_start_date = '2025-12-25' OR
- task_claim_date = '2025-12-25' OR  
- task_end_date = '2025-12-25'

篩選條件：
- Plant = 'WJ2'
- Factory = 'NBU'  
- Line = 'E5'
- 日期 = 2025-12-25
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("=" * 80)
    print("Silver 層 vs Bronze 層 (FlowableTaskStats) L5 任務數比對")
    print("條件: CNE WJ2 NBU E5 | 日期: 2025-12-25")
    print("時間邏輯: task_start/claim/end_date 任一為 2025-12-25")
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
    print("📊 1. Bronze 層 (common_flowable_task_stats)")
    print("=" * 80)
    
    bronze_filter = f"""
        Plant = '{plant}'
        AND Factory = '{factory}'
        AND Line = '{line}'
        AND (
            toDate(TaskCreateTime) = '{target_date}'
            OR toDate(TaskClaimTime) = '{target_date}'
            OR toDate(TaskEndTime) = '{target_date}'
        )
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    """
    
    # Bronze 按狀態分布
    bronze_sql = f"""
        SELECT 
            TaskStatus,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {bronze_filter}
        GROUP BY TaskStatus
        ORDER BY cnt DESC
    """
    result = client.query(bronze_sql)
    
    bronze_done = 0
    bronze_doing = 0
    bronze_todo = 0
    bronze_total = 0
    
    print("\n   TaskStatus 分布:")
    for row in result.result_rows:
        status = row[0]
        cnt = row[1]
        print(f"      {status}: {cnt:,}")
        bronze_total += cnt
        if status.upper() == 'DONE':
            bronze_done = cnt
        elif status.upper() == 'DOING':
            bronze_doing = cnt
        elif status.upper() == 'TODO':
            bronze_todo = cnt
    
    print(f"   ---")
    print(f"   合計: {bronze_total:,}")
    
    # Bronze 按 Vx 分布
    bronze_vx_sql = f"""
        SELECT 
            substring(TaskDefinitionKey, 1, 2) as vx_type,
            TaskStatus,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {bronze_filter}
        GROUP BY vx_type, TaskStatus
        ORDER BY vx_type, TaskStatus
    """
    result = client.query(bronze_vx_sql)
    print("\n   Vx x TaskStatus 分布:")
    current_vx = None
    for row in result.result_rows:
        vx = row[0]
        status = row[1]
        cnt = row[2]
        if vx != current_vx:
            print(f"   [{vx}]")
            current_vx = vx
        print(f"      {status}: {cnt}")
    
    # ========================================
    # 2. Silver 層查詢 (使用相同的 OR 時間邏輯)
    # ========================================
    print("\n" + "=" * 80)
    print("📊 2. Silver 層 (mv_fact_task_vx)")
    print("=" * 80)
    
    # 使用相同的 OR 時間邏輯
    silver_filter = f"""
        plant = '{plant}'
        AND factory = '{factory}'
        AND line = '{line}'
        AND (
            task_start_date = '{target_date}'
            OR task_claim_date = '{target_date}'
            OR task_end_date = '{target_date}'
        )
        AND is_excluded = 0
    """
    
    # Silver 按狀態分布
    silver_sql = f"""
        SELECT 
            task_status,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE {silver_filter}
        GROUP BY task_status
        ORDER BY cnt DESC
    """
    result = client.query(silver_sql)
    
    silver_done = 0
    silver_doing = 0
    silver_todo = 0
    silver_total = 0
    
    print("\n   task_status 分布:")
    for row in result.result_rows:
        status = row[0]
        cnt = row[1]
        print(f"      {status}: {cnt:,}")
        silver_total += cnt
        if status.upper() == 'DONE':
            silver_done = cnt
        elif status.upper() == 'DOING':
            silver_doing = cnt
        elif status.upper() == 'TODO':
            silver_todo = cnt
    
    print(f"   ---")
    print(f"   合計: {silver_total:,}")
    
    # Silver 按 Vx 分布
    silver_vx_sql = f"""
        SELECT 
            vx_type,
            task_status,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE {silver_filter}
        GROUP BY vx_type, task_status
        ORDER BY vx_type, task_status
    """
    result = client.query(silver_vx_sql)
    print("\n   vx_type x task_status 分布:")
    current_vx = None
    for row in result.result_rows:
        vx = row[0]
        status = row[1]
        cnt = row[2]
        if vx != current_vx:
            print(f"   [{vx}]")
            current_vx = vx
        print(f"      {status}: {cnt}")
    
    # ========================================
    # 3. 差異比對
    # ========================================
    print("\n" + "=" * 80)
    print("📊 3. 差異比對結果")
    print("=" * 80)
    
    print("\n   | 指標 | Bronze (FlowableTaskStats) | Silver (mv_fact_task_vx) | 差異 |")
    print("   |------|---------------------------|-------------------------|------|")
    print(f"   | Total | {bronze_total:,} | {silver_total:,} | {bronze_total - silver_total:+,} |")
    print(f"   | TODO | {bronze_todo:,} | {silver_todo:,} | {bronze_todo - silver_todo:+,} |")
    print(f"   | DOING | {bronze_doing:,} | {silver_doing:,} | {bronze_doing - silver_doing:+,} |")
    print(f"   | DONE | {bronze_done:,} | {silver_done:,} | {bronze_done - silver_done:+,} |")
    
    # 判斷是否一致
    total_match = bronze_total == silver_total
    todo_match = bronze_todo == silver_todo
    doing_match = bronze_doing == silver_doing
    done_match = bronze_done == silver_done
    
    all_match = total_match and todo_match and doing_match and done_match
    
    print("\n" + "=" * 80)
    if all_match:
        print("✅ 結論: Silver 層與 Bronze 層 (FlowableTaskStats) 數據完全一致！")
    else:
        print("⚠️ 結論: Silver 層與 Bronze 層 (FlowableTaskStats) 數據存在差異")
        
        # 進一步分析差異原因
        print("\n" + "=" * 80)
        print("📊 4. 差異分析")
        print("=" * 80)
        
        # 檢查 is_excluded 的影響
        excluded_sql = f"""
            SELECT 
                exclude_reason,
                count() as cnt
            FROM silver.mv_fact_task_vx FINAL
            WHERE plant = '{plant}'
              AND factory = '{factory}'
              AND line = '{line}'
              AND (
                  task_start_date = '{target_date}'
                  OR task_claim_date = '{target_date}'
                  OR task_end_date = '{target_date}'
              )
              AND is_excluded = 1
            GROUP BY exclude_reason
            ORDER BY cnt DESC
        """
        result = client.query(excluded_sql)
        print("\n   Silver 層排除的任務 (is_excluded=1):")
        silver_excluded = 0
        for row in result.result_rows:
            reason = row[0] or 'NULL'
            cnt = row[1]
            print(f"      {reason}: {cnt}")
            silver_excluded += cnt
        print(f"   排除任務總計: {silver_excluded}")
        
        # 檢查 Bronze 層 bypass
        bypass_sql = f"""
            SELECT count() as cnt
            FROM bronze.common_flowable_task_stats FINAL
            WHERE Plant = '{plant}'
              AND Factory = '{factory}'
              AND Line = '{line}'
              AND (
                  toDate(TaskCreateTime) = '{target_date}'
                  OR toDate(TaskClaimTime) = '{target_date}'
                  OR toDate(TaskEndTime) = '{target_date}'
              )
              AND TaskBypass = 'Y'
        """
        bronze_bypass = client.command(bypass_sql)
        print(f"\n   Bronze 層 bypass 任務: {bronze_bypass}")
        
        # 對比說明
        print("\n   📋 差異可能原因:")
        print("   1. FlowableTaskStats 與 BPM 原生表的資料更新時間差異")
        print("   2. is_excluded 判斷邏輯 (包含 E/C 開頭、Q/R 工單) vs TaskBypass")
        print("   3. FlowableTaskStats 是聚合表，可能有資料延遲")
    
    # ========================================
    # 5. 樣本資料比對
    # ========================================
    print("\n" + "=" * 80)
    print("📊 5. 樣本資料比對 (前5筆)")
    print("=" * 80)
    
    # Bronze 樣本
    print("\n   Bronze (FlowableTaskStats):")
    bronze_sample_sql = f"""
        SELECT 
            TaskId,
            TaskDefinitionKey,
            TaskStatus,
            toDate(TaskCreateTime) as create_date,
            toDate(TaskClaimTime) as claim_date,
            toDate(TaskEndTime) as end_date
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {bronze_filter}
        ORDER BY TaskId
        LIMIT 5
    """
    result = client.query(bronze_sample_sql)
    for row in result.result_rows:
        print(f"      {row[1]} | {row[2]} | start={row[3]} claim={row[4]} end={row[5]}")
    
    # Silver 樣本
    print("\n   Silver (mv_fact_task_vx):")
    silver_sample_sql = f"""
        SELECT 
            task_id,
            task_definition_key,
            task_status,
            task_start_date,
            task_claim_date,
            task_end_date
        FROM silver.mv_fact_task_vx FINAL
        WHERE {silver_filter}
        ORDER BY task_id
        LIMIT 5
    """
    result = client.query(silver_sample_sql)
    for row in result.result_rows:
        print(f"      {row[1]} | {row[2]} | start={row[3]} claim={row[4]} end={row[5]}")
    
    print("\n" + "=" * 80)
    client.close()

if __name__ == "__main__":
    main()
