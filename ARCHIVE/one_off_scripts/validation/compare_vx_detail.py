#!/usr/bin/env python3
"""
深入分析 FlowableTaskStats vs Silver 層 Vx 分布差異
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)

    print("=" * 80)
    print("深入分析 FlowableTaskStats vs Silver 層 Vx 分布差異")
    print("=" * 80)

    # 1. 確認時間範圍
    print("\n1. 時間範圍比對:")
    
    print("   FlowableTaskStats 時間範圍:")
    result = client.query("""
        SELECT 
            min(TaskCreateDate) as min_date,
            max(TaskCreateDate) as max_date,
            count() as total
        FROM bronze.common_flowable_task_stats FINAL
    """)
    if result.result_rows:
        row = result.result_rows[0]
        print(f"     {row[0]} ~ {row[1]} ({row[2]:,} 筆)")
        flowable_min = row[0]
        flowable_max = row[1]
    
    print("   Silver 層 (mv_fact_task_vx) 時間範圍:")
    result = client.query("""
        SELECT 
            min(task_create_date) as min_date,
            max(task_create_date) as max_date,
            count() as total
        FROM silver.mv_fact_task_vx FINAL
    """)
    if result.result_rows:
        row = result.result_rows[0]
        print(f"     {row[0]} ~ {row[1]} ({row[2]:,} 筆)")

    # 2. 在相同時間範圍內比對
    print("\n2. 在 FlowableTaskStats 時間範圍內比對 (同時間窗口):")
    
    print(f"   限制時間範圍: {flowable_min} ~ {flowable_max}")
    
    print("\n   FlowableTaskStats Vx 分布:")
    result = client.query("""
        SELECT 
            CASE 
                WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
                WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
                WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
                ELSE 'Other'
            END AS vx,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY vx ORDER BY vx
    """)
    flowable_vx = {}
    for row in result.result_rows:
        flowable_vx[row[0]] = row[1]
        print(f"     {row[0]}: {row[1]:,}")
    
    print("\n   Silver 層 Vx 分布 (相同時間範圍，含 is_excluded):")
    result = client.query(f"""
        SELECT 
            vx_type,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_create_date >= '{flowable_min}' 
          AND task_create_date <= '{flowable_max}'
        GROUP BY vx_type ORDER BY vx_type
    """)
    silver_vx_all = {}
    for row in result.result_rows:
        silver_vx_all[row[0]] = row[1]
        print(f"     {row[0]}: {row[1]:,}")
    
    print("\n   Silver 層 Vx 分布 (相同時間範圍，排除 is_excluded=1):")
    result = client.query(f"""
        SELECT 
            vx_type,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_create_date >= '{flowable_min}' 
          AND task_create_date <= '{flowable_max}'
          AND is_excluded = 0
        GROUP BY vx_type ORDER BY vx_type
    """)
    silver_vx_filtered = {}
    for row in result.result_rows:
        silver_vx_filtered[row[0]] = row[1]
        print(f"     {row[0]}: {row[1]:,}")

    # 3. FlowableTaskStats 的 TaskBypass 分布
    print("\n3. FlowableTaskStats 的 TaskBypass 分布:")
    result = client.query("""
        SELECT TaskBypass, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY TaskBypass
    """)
    for row in result.result_rows:
        print(f"     TaskBypass='{row[0]}': {row[1]:,}")
    
    # 4. 排除 TaskBypass 後的比對
    print("\n4. FlowableTaskStats (排除 TaskBypass='Y') Vx 分布:")
    result = client.query("""
        SELECT 
            CASE 
                WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
                WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
                WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
                ELSE 'Other'
            END AS vx,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE TaskBypass != 'Y' OR TaskBypass IS NULL
        GROUP BY vx ORDER BY vx
    """)
    for row in result.result_rows:
        print(f"     {row[0]}: {row[1]:,}")

    # 5. 檢查 Plant 分布差異
    print("\n5. Plant 分布比對 (相同時間範圍):")
    print("   FlowableTaskStats 前 5 Plant:")
    result = client.query("""
        SELECT Plant, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY Plant ORDER BY cnt DESC LIMIT 5
    """)
    for row in result.result_rows:
        print(f"     {row[0]}: {row[1]:,}")
    
    print("   Silver 層前 5 Plant:")
    result = client.query(f"""
        SELECT plant, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_create_date >= '{flowable_min}' 
          AND task_create_date <= '{flowable_max}'
        GROUP BY plant ORDER BY cnt DESC LIMIT 5
    """)
    for row in result.result_rows:
        print(f"     {row[0]}: {row[1]:,}")

    # 6. 結論
    print("\n" + "=" * 80)
    print("6. 差異分析結論:")
    print("-" * 80)
    
    # 計算差異
    for vx in ['V1', 'V2', 'V3']:
        f_cnt = flowable_vx.get(vx, 0)
        s_cnt = silver_vx_filtered.get(vx, 0)
        diff = s_cnt - f_cnt
        pct = (diff / f_cnt * 100) if f_cnt > 0 else 0
        status = "✅" if abs(pct) < 10 else "⚠️"
        print(f"   {status} {vx}: FlowableTaskStats={f_cnt:,}, Silver={s_cnt:,}, 差異={diff:+,} ({pct:+.1f}%)")
    
    print("\n" + "=" * 80)

    client.close()

if __name__ == "__main__":
    main()
