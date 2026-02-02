#!/usr/bin/env python3
"""
在相同時間範圍和相同 Plant 條件下比對 Vx 分布
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
    print("在相同時間範圍 + 相同 Plant 條件下比對 Vx 分布")
    print("=" * 80)

    # 1. 取得 FlowableTaskStats 的 Plant 清單
    print("\n1. FlowableTaskStats 包含的 Plant:")
    result = client.query("""
        SELECT Plant, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY Plant ORDER BY cnt DESC
    """)
    flowable_plants = [row[0] for row in result.result_rows if row[0]]
    for row in result.result_rows:
        print(f"     {row[0]}: {row[1]:,}")
    
    # 取得時間範圍
    result = client.query("""
        SELECT min(TaskCreateDate), max(TaskCreateDate)
        FROM bronze.common_flowable_task_stats FINAL
    """)
    min_date, max_date = result.result_rows[0]
    
    # 建立 Plant 過濾條件
    plant_filter = ", ".join([f"'{p}'" for p in flowable_plants if p])
    
    print(f"\n2. 條件設定:")
    print(f"   時間範圍: {min_date} ~ {max_date}")
    print(f"   Plant 過濾: {plant_filter[:80]}...")

    # 3. FlowableTaskStats Vx 分布 (排除 TaskBypass='Y')
    print("\n3. FlowableTaskStats Vx 分布 (排除 TaskBypass='Y'):")
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
        WHERE (TaskBypass != 'Y' OR TaskBypass IS NULL)
        GROUP BY vx ORDER BY vx
    """)
    flowable_vx = {}
    for row in result.result_rows:
        flowable_vx[row[0]] = row[1]
        print(f"     {row[0]}: {row[1]:,}")
    
    # 4. Silver 層在相同條件下的 Vx 分布
    print("\n4. Silver 層 Vx 分布 (相同 Plant + 時間 + 排除 is_excluded=1):")
    query = f"""
        SELECT 
            vx_type,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_create_date >= '{min_date}' 
          AND task_create_date <= '{max_date}'
          AND plant IN ({plant_filter})
          AND is_excluded = 0
        GROUP BY vx_type ORDER BY vx_type
    """
    result = client.query(query)
    silver_vx = {}
    for row in result.result_rows:
        silver_vx[row[0]] = row[1]
        print(f"     {row[0]}: {row[1]:,}")

    # 5. 總量比對
    print("\n5. 總量比對:")
    flowable_total = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE (TaskBypass != 'Y' OR TaskBypass IS NULL)
    """)
    
    silver_total = client.command(f"""
        SELECT count() FROM silver.mv_fact_task_vx FINAL
        WHERE task_create_date >= '{min_date}' 
          AND task_create_date <= '{max_date}'
          AND plant IN ({plant_filter})
          AND is_excluded = 0
    """)
    
    print(f"     FlowableTaskStats (排除 bypass): {flowable_total:,}")
    print(f"     Silver 層 (相同條件): {silver_total:,}")
    print(f"     差異: {silver_total - flowable_total:+,} ({(silver_total - flowable_total) / flowable_total * 100:+.1f}%)")

    # 6. 按 Vx 比對
    print("\n" + "=" * 80)
    print("6. Vx 比對結果:")
    print("-" * 80)
    
    for vx in ['V1', 'V2', 'V3', 'Other']:
        f_cnt = flowable_vx.get(vx, 0)
        s_cnt = silver_vx.get(vx, 0)
        if f_cnt > 0:
            diff = s_cnt - f_cnt
            pct = (diff / f_cnt * 100)
            status = "✅" if abs(pct) < 10 else "⚠️"
            print(f"   {status} {vx}: FlowableTaskStats={f_cnt:,}, Silver={s_cnt:,}, 差異={diff:+,} ({pct:+.1f}%)")
        else:
            print(f"   ℹ️  {vx}: FlowableTaskStats=0, Silver={s_cnt:,}")

    # 7. 按 Plant 細分比對
    print("\n7. 按 Plant 分別比對:")
    for plant in flowable_plants[:5]:  # 只看前 5 個 Plant
        if not plant:
            continue
            
        # FlowableTaskStats
        f_count = client.command(f"""
            SELECT count() FROM bronze.common_flowable_task_stats FINAL
            WHERE Plant = '{plant}' AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
        """)
        
        # Silver
        s_count = client.command(f"""
            SELECT count() FROM silver.mv_fact_task_vx FINAL
            WHERE plant = '{plant}'
              AND task_create_date >= '{min_date}' 
              AND task_create_date <= '{max_date}'
              AND is_excluded = 0
        """)
        
        if f_count > 0:
            diff_pct = (s_count - f_count) / f_count * 100
            status = "✅" if abs(diff_pct) < 10 else "⚠️"
        else:
            diff_pct = 0
            status = "ℹ️ "
        
        print(f"   {status} {plant}: FlowableTaskStats={f_count:,}, Silver={s_count:,} ({diff_pct:+.1f}%)")

    print("\n" + "=" * 80)

    client.close()

if __name__ == "__main__":
    main()
