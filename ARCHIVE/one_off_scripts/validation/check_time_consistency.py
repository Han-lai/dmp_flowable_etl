#!/usr/bin/env python3
"""
時間範圍解讀一致性檢查

確認 Bronze (FlowableTaskStats) 和 Silver (mv_fact_task_vx) 的時間篩選邏輯是否一致

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
    print("時間範圍解讀一致性檢查")
    print("條件: CNE WJ2 NBU E5 | 日期: 2025-12-25")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-12-25'
    
    # ========================================
    # 1. 分析 Bronze 層時間欄位名稱
    # ========================================
    print("\n" + "=" * 80)
    print("📊 1. Bronze 層欄位分析")
    print("=" * 80)
    
    # 查看時間相關欄位
    cols_sql = """
        SELECT name, type 
        FROM system.columns 
        WHERE database = 'bronze' AND table = 'common_flowable_task_stats'
          AND (name LIKE '%Time%' OR name LIKE '%Date%')
        ORDER BY position
    """
    result = client.query(cols_sql)
    print("\n   時間相關欄位:")
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]}")
    
    # ========================================
    # 2. 分析 Silver 層時間欄位名稱
    # ========================================
    print("\n" + "=" * 80)
    print("📊 2. Silver 層欄位分析")
    print("=" * 80)
    
    cols_sql = """
        SELECT name, type 
        FROM system.columns 
        WHERE database = 'silver' AND table = 'mv_fact_task_vx'
          AND (name LIKE '%time%' OR name LIKE '%date%')
        ORDER BY position
    """
    result = client.query(cols_sql)
    print("\n   時間相關欄位:")
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]}")
    
    # ========================================
    # 3. 詳細檢查各時間條件的匹配數量
    # ========================================
    print("\n" + "=" * 80)
    print("📊 3. 各時間條件的匹配數量分析")
    print("=" * 80)
    
    base_filter = f"Plant = '{plant}' AND Factory = '{factory}' AND Line = '{line}' AND (TaskBypass = 'N' OR TaskBypass IS NULL)"
    
    # Bronze 各時間條件
    print("\n   Bronze 層 (FlowableTaskStats):")
    
    time_conditions = [
        ("TaskCreateTime", f"toDate(TaskCreateTime) = '{target_date}'"),
        ("TaskClaimTime", f"toDate(TaskClaimTime) = '{target_date}'"),
        ("TaskEndTime", f"toDate(TaskEndTime) = '{target_date}'"),
        ("任一時間 (OR)", f"(toDate(TaskCreateTime) = '{target_date}' OR toDate(TaskClaimTime) = '{target_date}' OR toDate(TaskEndTime) = '{target_date}')"),
    ]
    
    for name, cond in time_conditions:
        sql = f"SELECT count() FROM bronze.common_flowable_task_stats FINAL WHERE {base_filter} AND {cond}"
        cnt = client.command(sql)
        print(f"      {name}: {cnt:,}")
    
    # Silver 各時間條件
    print("\n   Silver 層 (mv_fact_task_vx):")
    
    silver_base = f"plant = '{plant}' AND factory = '{factory}' AND line = '{line}' AND is_excluded = 0"
    
    silver_conditions = [
        ("task_start_date", f"task_start_date = '{target_date}'"),
        ("task_claim_date", f"task_claim_date = '{target_date}'"),
        ("task_end_date", f"task_end_date = '{target_date}'"),
        ("task_create_date", f"task_create_date = '{target_date}'"),
        ("任一時間 (OR)", f"(task_start_date = '{target_date}' OR task_claim_date = '{target_date}' OR task_end_date = '{target_date}')"),
    ]
    
    for name, cond in silver_conditions:
        sql = f"SELECT count() FROM silver.mv_fact_task_vx FINAL WHERE {silver_base} AND {cond}"
        cnt = client.command(sql)
        print(f"      {name}: {cnt:,}")
    
    # ========================================
    # 4. 檢查時間欄位映射
    # ========================================
    print("\n" + "=" * 80)
    print("📊 4. 時間欄位映射確認")
    print("=" * 80)
    
    print("\n   預期映射關係:")
    print("   Bronze (FlowableTaskStats)    →    Silver (mv_fact_task_vx)")
    print("   -------------------------------------------------------")
    print("   TaskCreateTime                →    task_start_date (來自 START_TIME_)")
    print("   TaskClaimTime                 →    task_claim_date (來自 CLAIM_TIME_)")
    print("   TaskEndTime                   →    task_end_date (來自 END_TIME_)")
    
    # ========================================
    # 5. 檢查是否是維度過濾問題
    # ========================================
    print("\n" + "=" * 80)
    print("📊 5. 維度過濾檢查 (不含 Line 條件)")
    print("=" * 80)
    
    # 不含 Line 的 Bronze 查詢
    bronze_no_line = f"""
        SELECT count() 
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant = '{plant}'
          AND Factory = '{factory}'
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
          AND (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
    """
    bronze_no_line_cnt = client.command(bronze_no_line)
    print(f"\n   Bronze (不含 Line 條件): {bronze_no_line_cnt:,}")
    
    # 不含 line 的 Silver 查詢
    silver_no_line = f"""
        SELECT count() 
        FROM silver.mv_fact_task_vx FINAL
        WHERE plant = '{plant}'
          AND factory = '{factory}'
          AND is_excluded = 0
          AND (task_start_date = '{target_date}' 
               OR task_claim_date = '{target_date}' 
               OR task_end_date = '{target_date}')
    """
    silver_no_line_cnt = client.command(silver_no_line)
    print(f"   Silver (不含 line 條件): {silver_no_line_cnt:,}")
    
    # ========================================
    # 6. 檢查 Line 欄位值差異
    # ========================================
    print("\n" + "=" * 80)
    print("📊 6. Line 欄位值檢查")
    print("=" * 80)
    
    # Bronze Line 值
    bronze_line_sql = f"""
        SELECT Line, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant = '{plant}'
          AND Factory = '{factory}'
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
          AND (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
        GROUP BY Line
        ORDER BY cnt DESC
        LIMIT 10
    """
    result = client.query(bronze_line_sql)
    print(f"\n   Bronze Layer - Line 分布 (前10):")
    for row in result.result_rows:
        line_val = row[0] or 'NULL'
        print(f"      '{line_val}': {row[1]:,}")
    
    # Silver line 值
    silver_line_sql = f"""
        SELECT line, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE plant = '{plant}'
          AND factory = '{factory}'
          AND is_excluded = 0
          AND (task_start_date = '{target_date}' 
               OR task_claim_date = '{target_date}' 
               OR task_end_date = '{target_date}')
        GROUP BY line
        ORDER BY cnt DESC
        LIMIT 10
    """
    result = client.query(silver_line_sql)
    print(f"\n   Silver Layer - line 分布 (前10):")
    for row in result.result_rows:
        line_val = row[0] or 'NULL'
        print(f"      '{line_val}': {row[1]:,}")
    
    # ========================================
    # 7. 直接比對 Task ID
    # ========================================
    print("\n" + "=" * 80)
    print("📊 7. Task ID 交集分析")
    print("=" * 80)
    
    # Bronze 的 Task ID
    bronze_ids_sql = f"""
        SELECT TaskId
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant = '{plant}'
          AND Factory = '{factory}'
          AND Line = '{line}'
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
          AND (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
    """
    bronze_ids = client.query(bronze_ids_sql)
    bronze_id_set = set(row[0] for row in bronze_ids.result_rows)
    print(f"\n   Bronze Task ID 數量: {len(bronze_id_set)}")
    
    # Silver 的 task_id
    silver_ids_sql = f"""
        SELECT task_id
        FROM silver.mv_fact_task_vx FINAL
        WHERE plant = '{plant}'
          AND factory = '{factory}'
          AND line = '{line}'
          AND is_excluded = 0
          AND (task_start_date = '{target_date}' 
               OR task_claim_date = '{target_date}' 
               OR task_end_date = '{target_date}')
    """
    silver_ids = client.query(silver_ids_sql)
    silver_id_set = set(row[0] for row in silver_ids.result_rows)
    print(f"   Silver task_id 數量: {len(silver_id_set)}")
    
    # 交集
    intersection = bronze_id_set & silver_id_set
    bronze_only = bronze_id_set - silver_id_set
    silver_only = silver_id_set - bronze_id_set
    
    print(f"\n   交集 (兩邊都有): {len(intersection)}")
    print(f"   僅 Bronze 有: {len(bronze_only)}")
    print(f"   僅 Silver 有: {len(silver_only)}")
    
    if bronze_only:
        print(f"\n   僅 Bronze 有的 Task ID (前5):")
        for tid in list(bronze_only)[:5]:
            print(f"      {tid}")
    
    if silver_only:
        print(f"\n   僅 Silver 有的 task_id (前5):")
        for tid in list(silver_only)[:5]:
            print(f"      {tid}")
    
    print("\n" + "=" * 80)
    client.close()

if __name__ == "__main__":
    main()
