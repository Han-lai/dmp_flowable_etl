#!/usr/bin/env python3
"""
FlowableTaskStats 反向工程分析

目標: 找出 FlowableTaskStats 與 Bronze 層的差異，推測其計算邏輯
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
    print("FlowableTaskStats 反向工程分析")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # ========================================
    # 1. FlowableTaskStats 欄位結構分析
    # ========================================
    print("\n" + "=" * 80)
    print("📊 1. FlowableTaskStats 欄位結構")
    print("=" * 80)
    
    cols_sql = """
        SELECT name, type 
        FROM system.columns 
        WHERE database = 'bronze' AND table = 'common_flowable_task_stats'
        ORDER BY position
    """
    result = client.query(cols_sql)
    print("\n   所有欄位:")
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]}")
    
    # ========================================
    # 2. 資料量比對
    # ========================================
    print("\n" + "=" * 80)
    print("📊 2. 資料量比對")
    print("=" * 80)
    
    flowable_total = client.command("SELECT count() FROM bronze.common_flowable_task_stats FINAL")
    bpm_total = client.command("SELECT count() FROM bronze.bpm_act_hi_taskinst")
    
    print(f"\n   FlowableTaskStats: {flowable_total:,}")
    print(f"   bpm_act_hi_taskinst: {bpm_total:,}")
    print(f"   差異: {bpm_total - flowable_total:,} ({(bpm_total - flowable_total) / bpm_total * 100:.1f}%)")
    
    # ========================================
    # 3. 關鍵欄位分布分析
    # ========================================
    print("\n" + "=" * 80)
    print("📊 3. FlowableTaskStats 關鍵欄位分布")
    print("=" * 80)
    
    # TaskBypass 分布
    print("\n   TaskBypass 分布:")
    result = client.query("""
        SELECT TaskBypass, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY TaskBypass
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"      '{row[0]}': {row[1]:,}")
    
    # TaskStatus 分布
    print("\n   TaskStatus 分布:")
    result = client.query("""
        SELECT TaskStatus, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY TaskStatus
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"      '{row[0]}': {row[1]:,}")
    
    # ProcessTeam 分布 (可能的過濾條件)
    print("\n   ProcessTeam 分布:")
    result = client.query("""
        SELECT ProcessTeam, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY ProcessTeam
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(f"      '{row[0]}': {row[1]:,}")
    
    # TaskDefinitionKey 前綴分布
    print("\n   TaskDefinitionKey 前綴分布 (Vx類型):")
    result = client.query("""
        SELECT 
            substring(TaskDefinitionKey, 1, 2) as vx_prefix,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY vx_prefix
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(f"      '{row[0]}': {row[1]:,}")
    
    # ========================================
    # 4. BPM 原生表的 TaskDefinitionKey 分布
    # ========================================
    print("\n" + "=" * 80)
    print("📊 4. BPM 原生表 TaskDefinitionKey 前綴分布")
    print("=" * 80)
    
    result = client.query("""
        SELECT 
            substring(TASK_DEF_KEY_, 1, 2) as vx_prefix,
            count() as cnt
        FROM bronze.bpm_act_hi_taskinst
        GROUP BY vx_prefix
        ORDER BY cnt DESC
        LIMIT 15
    """)
    for row in result.result_rows:
        print(f"      '{row[0]}': {row[1]:,}")
    
    # ========================================
    # 5. 找出 BPM 有但 FlowableTaskStats 沒有的 prefix
    # ========================================
    print("\n" + "=" * 80)
    print("📊 5. 可能被 FlowableTaskStats 排除的類型")
    print("=" * 80)
    
    # 比較兩邊的 prefix
    flowable_prefix_sql = """
        SELECT DISTINCT substring(TaskDefinitionKey, 1, 2) as prefix
        FROM bronze.common_flowable_task_stats FINAL
    """
    bpm_prefix_sql = """
        SELECT DISTINCT substring(TASK_DEF_KEY_, 1, 2) as prefix
        FROM bronze.bpm_act_hi_taskinst
        WHERE TASK_DEF_KEY_ IS NOT NULL AND TASK_DEF_KEY_ != ''
    """
    
    flowable_prefixes = set(row[0] for row in client.query(flowable_prefix_sql).result_rows)
    bpm_prefixes = set(row[0] for row in client.query(bpm_prefix_sql).result_rows)
    
    only_in_bpm = bpm_prefixes - flowable_prefixes
    print(f"\n   FlowableTaskStats 包含的前綴: {sorted(flowable_prefixes)}")
    print(f"\n   僅在 BPM 有的前綴 (可能被排除): {sorted(only_in_bpm)}")
    
    # 計算這些被排除的數量
    if only_in_bpm:
        prefix_list = "', '".join(only_in_bpm)
        excluded_count = client.command(f"""
            SELECT count() FROM bronze.bpm_act_hi_taskinst
            WHERE substring(TASK_DEF_KEY_, 1, 2) IN ('{prefix_list}')
        """)
        print(f"\n   這些前綴在 BPM 的筆數: {excluded_count:,}")
    
    # ========================================
    # 6. 驗證案例: 2025-12-25 WJ2 NBU E5
    # ========================================
    print("\n" + "=" * 80)
    print("📊 6. 驗證案例: 2025-12-25 WJ2 NBU E5")
    print("=" * 80)
    
    target_date = '2025-12-25'
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    # FlowableTaskStats 查詢
    flowable_sql = f"""
        SELECT count()
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant = '{plant}'
          AND Factory = '{factory}'
          AND Line = '{line}'
          AND (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    """
    flowable_count = client.command(flowable_sql)
    print(f"\n   FlowableTaskStats (TaskBypass=N): {flowable_count}")
    
    # 逐步分解查詢
    print("\n   FlowableTaskStats 逐步分解:")
    
    # Step 1: 只有日期條件
    step1 = client.command(f"""
        SELECT count()
        FROM bronze.common_flowable_task_stats FINAL
        WHERE (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
    """)
    print(f"      [1] 日期條件: {step1:,}")
    
    # Step 2: 加上 TaskBypass
    step2 = client.command(f"""
        SELECT count()
        FROM bronze.common_flowable_task_stats FINAL
        WHERE (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    """)
    print(f"      [2] + TaskBypass=N: {step2:,}")
    
    # Step 3: 加上 Plant
    step3 = client.command(f"""
        SELECT count()
        FROM bronze.common_flowable_task_stats FINAL
        WHERE (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
          AND Plant = '{plant}'
    """)
    print(f"      [3] + Plant=WJ2: {step3:,}")
    
    # Step 4: 加上 Factory
    step4 = client.command(f"""
        SELECT count()
        FROM bronze.common_flowable_task_stats FINAL
        WHERE (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
          AND Plant = '{plant}'
          AND Factory = '{factory}'
    """)
    print(f"      [4] + Factory=NBU: {step4:,}")
    
    # Step 5: 加上 Line
    step5 = client.command(f"""
        SELECT count()
        FROM bronze.common_flowable_task_stats FINAL
        WHERE (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
          AND Plant = '{plant}'
          AND Factory = '{factory}'
          AND Line = '{line}'
    """)
    print(f"      [5] + Line=E5: {step5:,}")
    
    print("\n" + "=" * 80)
    client.close()

if __name__ == "__main__":
    main()
