#!/usr/bin/env python3
"""
2025-12-25 當天資料比對 (WJ2 + DG3)
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
    print("2025-12-25 當天資料比對 (WJ2 + DG3)")
    print("=" * 80)

    # FlowableTaskStats
    print("\n1. FlowableTaskStats (2025-12-25):")
    f_count = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant IN ('WJ2', 'DG3') AND TaskCreateDate = '2025-12-25'
    """)
    print(f"   總筆數: {f_count:,}")

    f_no_bypass = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant IN ('WJ2', 'DG3') 
          AND TaskCreateDate = '2025-12-25'
          AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
    """)
    print(f"   排除 bypass: {f_no_bypass:,}")

    # 狀態分布
    print("\n   TaskStatus 分布:")
    result = client.query("""
        SELECT TaskStatus, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant IN ('WJ2', 'DG3') 
          AND TaskCreateDate = '2025-12-25'
          AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
        GROUP BY TaskStatus ORDER BY cnt DESC
    """)
    f_status = {}
    for row in result.result_rows:
        f_status[row[0]] = row[1]
        print(f"      {row[0]}: {row[1]:,}")

    # Silver 層
    print("\n2. Silver 層 (2025-12-25):")
    s_count = client.command("""
        SELECT count() FROM silver.mv_fact_task_vx FINAL
        WHERE plant IN ('WJ2', 'DG3') AND task_create_date = '2025-12-25'
    """)
    print(f"   總筆數: {s_count:,}")

    s_no_excluded = client.command("""
        SELECT count() FROM silver.mv_fact_task_vx FINAL
        WHERE plant IN ('WJ2', 'DG3') 
          AND task_create_date = '2025-12-25'
          AND is_excluded = 0
    """)
    print(f"   排除 excluded: {s_no_excluded:,}")

    # 狀態分布
    print("\n   task_status 分布:")
    result = client.query("""
        SELECT task_status, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE plant IN ('WJ2', 'DG3') 
          AND task_create_date = '2025-12-25'
          AND is_excluded = 0
        GROUP BY task_status ORDER BY cnt DESC
    """)
    s_status = {}
    for row in result.result_rows:
        s_status[row[0]] = row[1]
        print(f"      {row[0]}: {row[1]:,}")

    # Vx 分布
    print("\n3. Vx 類型分布:")
    print("\n   FlowableTaskStats:")
    result = client.query("""
        SELECT 
            CASE 
                WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
                WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
                WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
                ELSE 'Other'
            END as vx,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant IN ('WJ2', 'DG3') 
          AND TaskCreateDate = '2025-12-25'
          AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
        GROUP BY vx ORDER BY cnt DESC
    """)
    f_vx = {}
    for row in result.result_rows:
        f_vx[row[0]] = row[1]
        print(f"      {row[0]}: {row[1]:,}")

    print("\n   Silver 層:")
    result = client.query("""
        SELECT vx_type, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE plant IN ('WJ2', 'DG3') 
          AND task_create_date = '2025-12-25'
          AND is_excluded = 0
        GROUP BY vx_type ORDER BY cnt DESC
    """)
    s_vx = {}
    for row in result.result_rows:
        s_vx[row[0]] = row[1]
        print(f"      {row[0]}: {row[1]:,}")

    # 比對結果
    print("\n" + "=" * 80)
    print("4. 比對結果:")
    print("-" * 80)
    
    diff = s_no_excluded - f_no_bypass
    pct = (diff / f_no_bypass * 100) if f_no_bypass > 0 else 0
    status = "✅" if abs(pct) < 10 else "⚠️"
    
    print(f"   FlowableTaskStats (排除 bypass): {f_no_bypass:,}")
    print(f"   Silver 層 (排除 excluded): {s_no_excluded:,}")
    print(f"   {status} 差異: {diff:+,} ({pct:+.1f}%)")

    # 狀態差異
    print("\n   狀態差異:")
    for st in ['DONE', 'TODO', 'DOING']:
        f = f_status.get(st, 0)
        s = s_status.get(st, 0)
        d = s - f
        print(f"      {st}: FlowableTaskStats={f:,}, Silver={s:,}, 差異={d:+,}")

    # Vx 差異
    print("\n   Vx 差異:")
    for vx in ['V1', 'V2', 'V3']:
        f = f_vx.get(vx, 0)
        s = s_vx.get(vx, 0)
        d = s - f
        p = (d / f * 100) if f > 0 else 0
        st = "✅" if abs(p) < 10 else "⚠️"
        print(f"      {st} {vx}: FlowableTaskStats={f:,}, Silver={s:,}, 差異={d:+,} ({p:+.1f}%)")

    print("\n" + "=" * 80)
    client.close()

if __name__ == "__main__":
    main()
