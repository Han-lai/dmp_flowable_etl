#!/usr/bin/env python3
"""
FlowableTaskStats 完整排除邏輯分析
目標：找出讓 ClickHouse 查詢結果對齊 FlowableTaskStats 18,343 筆的過濾條件
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)

    print("=" * 80)
    print("FlowableTaskStats 完整排除邏輯分析")
    print("目標: 找出讓 ClickHouse 結果對齊 18,343 筆的過濾條件")
    print("=" * 80)

    # ============================================
    # 1. 分析 FlowableTaskStats 的欄位特性
    # ============================================
    print("\n1. FlowableTaskStats 欄位分析:")
    
    # TaskBypass 分布
    print("\n   a) TaskBypass 分布:")
    result = client.query("""
        SELECT TaskBypass, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY TaskBypass
    """)
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]:,}")

    # TaskStatus 分布
    print("\n   b) TaskStatus 分布:")
    result = client.query("""
        SELECT TaskStatus, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY TaskStatus
    """)
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]:,}")

    # DeleteReason 分布
    print("\n   c) DeleteReason 分布 (非空):")
    result = client.query("""
        SELECT DeleteReason, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE DeleteReason IS NOT NULL AND DeleteReason != ''
        GROUP BY DeleteReason
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]:,}")
    
    delete_reason_count = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE DeleteReason IS NOT NULL AND DeleteReason != ''
    """)
    print(f"      (共 {delete_reason_count:,} 筆有 DeleteReason)")

    # TaskDefinitionKey 前綴分布
    print("\n   d) TaskDefinitionKey 前綴分布:")
    result = client.query("""
        SELECT 
            substring(TaskDefinitionKey, 1, 2) as prefix,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY prefix
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]:,}")

    # MoNumber 前綴分布
    print("\n   e) MoNumber 前綴分布:")
    result = client.query("""
        SELECT 
            substring(MoNumber, 1, 1) as prefix,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE MoNumber IS NOT NULL AND MoNumber != ''
        GROUP BY prefix
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]:,}")

    # ============================================
    # 2. 找出 18,343 筆的查詢條件
    # ============================================
    print("\n" + "=" * 80)
    print("2. 嘗試不同過濾條件組合:")
    print("-" * 80)

    # 條件 1: 只排除 TaskBypass = 'Y'
    count1 = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE TaskBypass != 'Y' OR TaskBypass IS NULL
    """)
    print(f"   排除 TaskBypass='Y': {count1:,}")

    # 條件 2: 排除 TaskBypass + 排除 E%/C%
    count2 = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE (TaskBypass != 'Y' OR TaskBypass IS NULL)
          AND TaskDefinitionKey NOT LIKE 'E%'
          AND TaskDefinitionKey NOT LIKE 'C%'
    """)
    print(f"   排除 TaskBypass + E%/C%: {count2:,}")

    # 條件 3: 排除 DeleteReason 非空
    count3 = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE (TaskBypass != 'Y' OR TaskBypass IS NULL)
          AND (DeleteReason IS NULL OR DeleteReason = '')
    """)
    print(f"   排除 TaskBypass + DeleteReason: {count3:,}")

    # 條件 4: 特定時間範圍
    count4 = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE TaskCreateDate = '2025-12-25'
    """)
    print(f"   2025-12-25 當天: {count4:,}")

    # 條件 5: 特定 Plant
    print("\n   特定 Plant 組合:")
    for plant in ['WJ2', 'DG3', 'DET6']:
        count = client.command(f"""
            SELECT count() FROM bronze.common_flowable_task_stats FINAL
            WHERE Plant = '{plant}'
        """)
        print(f"      {plant}: {count:,}")

    # 條件 6: WJ2 + 排除 bypass
    count6 = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant = 'WJ2'
          AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
    """)
    print(f"\n   WJ2 + 排除 bypass: {count6:,}")

    # 條件 7: WJ2 + 特定日期
    count7 = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant = 'WJ2'
          AND TaskCreateDate = '2025-12-25'
    """)
    print(f"   WJ2 + 2025-12-25: {count7:,}")

    # 條件 8: 特定日期範圍
    print("\n   不同日期範圍:")
    for days in [1, 7, 14, 30]:
        count = client.command(f"""
            SELECT count() FROM bronze.common_flowable_task_stats FINAL
            WHERE TaskCreateDate >= today() - {days}
              AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
        """)
        print(f"      過去 {days} 天 (排除 bypass): {count:,}")

    # ============================================
    # 3. 尋找接近 18,343 的條件
    # ============================================
    print("\n" + "=" * 80)
    print("3. 尋找接近 18,343 的條件組合:")
    print("-" * 80)

    # 嘗試不同 Plant + 條件
    conditions = [
        ("WJ2 全部", "Plant = 'WJ2'"),
        ("WJ2 排除bypass", "Plant = 'WJ2' AND (TaskBypass != 'Y' OR TaskBypass IS NULL)"),
        ("WJ2 排除bypass+E/C", "Plant = 'WJ2' AND (TaskBypass != 'Y' OR TaskBypass IS NULL) AND TaskDefinitionKey NOT LIKE 'E%' AND TaskDefinitionKey NOT LIKE 'C%'"),
        ("DG3 全部", "Plant = 'DG3'"),
        ("DG3 排除bypass", "Plant = 'DG3' AND (TaskBypass != 'Y' OR TaskBypass IS NULL)"),
        ("V2 全部", "TaskDefinitionKey LIKE 'V2%'"),
        ("V2 排除bypass", "TaskDefinitionKey LIKE 'V2%' AND (TaskBypass != 'Y' OR TaskBypass IS NULL)"),
        ("V3 全部", "TaskDefinitionKey LIKE 'V3%'"),
        ("V3 排除bypass", "TaskDefinitionKey LIKE 'V3%' AND (TaskBypass != 'Y' OR TaskBypass IS NULL)"),
    ]
    
    target = 18343
    closest = []
    
    for name, cond in conditions:
        count = client.command(f"""
            SELECT count() FROM bronze.common_flowable_task_stats FINAL
            WHERE {cond}
        """)
        diff = abs(count - target)
        closest.append((name, count, diff))
        match = "🎯" if diff < 1000 else ("✅" if diff < 5000 else "")
        print(f"   {match} {name}: {count:,} (差異: {diff:,})")
    
    # ============================================
    # 4. Silver 層比對
    # ============================================
    print("\n" + "=" * 80)
    print("4. Silver 層 (mv_fact_task_vx) 比對:")
    print("-" * 80)
    
    # 先確認 Silver 層的時間範圍
    result = client.query("""
        SELECT min(task_create_date), max(task_create_date), count()
        FROM silver.mv_fact_task_vx FINAL
    """)
    if result.result_rows:
        row = result.result_rows[0]
        print(f"   時間範圍: {row[0]} ~ {row[1]}")
        print(f"   總筆數: {row[2]:,}")

    # Silver 層各種條件
    silver_conditions = [
        ("全部", "1=1"),
        ("排除 is_excluded", "is_excluded = 0"),
        ("WJ2", "plant = 'WJ2'"),
        ("WJ2 + 排除excluded", "plant = 'WJ2' AND is_excluded = 0"),
        ("V2 類型", "vx_type = 'V2'"),
        ("V2 + 排除excluded", "vx_type = 'V2' AND is_excluded = 0"),
    ]
    
    for name, cond in silver_conditions:
        count = client.command(f"""
            SELECT count() FROM silver.mv_fact_task_vx FINAL
            WHERE {cond}
        """)
        diff = abs(count - target)
        match = "🎯" if diff < 1000 else ("✅" if diff < 5000 else "")
        print(f"   {match} {name}: {count:,} (差異: {diff:,})")

    print("\n" + "=" * 80)

    client.close()

if __name__ == "__main__":
    main()
