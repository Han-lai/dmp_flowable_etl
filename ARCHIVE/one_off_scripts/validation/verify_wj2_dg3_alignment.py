#!/usr/bin/env python3
"""
方案 C：只針對 WJ2, DG3 Plant 進行資料對齊驗證
比對 FlowableTaskStats vs Silver 層
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
    print("方案 C：WJ2, DG3 Plant 資料對齊驗證")
    print("=" * 80)

    plants = ['WJ2', 'DG3']
    
    # ============================================
    # 1. 總量比對 (只看 WJ2, DG3)
    # ============================================
    print("\n1. 總量比對 (WJ2 + DG3):")
    
    # FlowableTaskStats
    flowable_count = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant IN ('WJ2', 'DG3')
    """)
    print(f"   FlowableTaskStats: {flowable_count:,}")
    
    # Silver 層
    silver_count = client.command("""
        SELECT count() FROM silver.mv_fact_task_vx FINAL
        WHERE plant IN ('WJ2', 'DG3')
    """)
    print(f"   Silver 層: {silver_count:,}")
    
    diff = silver_count - flowable_count
    print(f"   差異: {diff:+,}")

    # ============================================
    # 2. 按 Plant 分別比對
    # ============================================
    print("\n2. 按 Plant 分別比對:")
    print("-" * 60)
    
    for plant in plants:
        # FlowableTaskStats
        f_total = client.command(f"""
            SELECT count() FROM bronze.common_flowable_task_stats FINAL
            WHERE Plant = '{plant}'
        """)
        
        f_no_bypass = client.command(f"""
            SELECT count() FROM bronze.common_flowable_task_stats FINAL
            WHERE Plant = '{plant}' AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
        """)
        
        # Silver 層
        s_total = client.command(f"""
            SELECT count() FROM silver.mv_fact_task_vx FINAL
            WHERE plant = '{plant}'
        """)
        
        s_no_excluded = client.command(f"""
            SELECT count() FROM silver.mv_fact_task_vx FINAL
            WHERE plant = '{plant}' AND is_excluded = 0
        """)
        
        print(f"\n   {plant}:")
        print(f"      FlowableTaskStats 全部: {f_total:,}")
        print(f"      FlowableTaskStats 排除bypass: {f_no_bypass:,}")
        print(f"      Silver 層全部: {s_total:,}")
        print(f"      Silver 層排除excluded: {s_no_excluded:,}")
        
        # 比對排除後的數量
        diff = s_no_excluded - f_no_bypass
        pct = (diff / f_no_bypass * 100) if f_no_bypass > 0 else 0
        status = "✅" if abs(pct) < 10 else "⚠️"
        print(f"      {status} 差異: {diff:+,} ({pct:+.1f}%)")

    # ============================================
    # 3. TaskStatus 比對
    # ============================================
    print("\n3. TaskStatus 分布比對 (WJ2 + DG3, 排除 bypass/excluded):")
    print("-" * 60)
    
    print("\n   FlowableTaskStats:")
    result = client.query("""
        SELECT TaskStatus, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant IN ('WJ2', 'DG3')
          AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
        GROUP BY TaskStatus ORDER BY cnt DESC
    """)
    flowable_status = {}
    for row in result.result_rows:
        flowable_status[row[0]] = row[1]
        print(f"      {row[0]}: {row[1]:,}")
    
    print("\n   Silver 層:")
    result = client.query("""
        SELECT task_status, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE plant IN ('WJ2', 'DG3') AND is_excluded = 0
        GROUP BY task_status ORDER BY cnt DESC
    """)
    silver_status = {}
    for row in result.result_rows:
        silver_status[row[0]] = row[1]
        print(f"      {row[0]}: {row[1]:,}")
    
    print("\n   狀態差異:")
    for status in ['DONE', 'TODO', 'DOING']:
        f_cnt = flowable_status.get(status, 0)
        s_cnt = silver_status.get(status, 0)
        diff = s_cnt - f_cnt
        print(f"      {status}: {diff:+,}")

    # ============================================
    # 4. Vx 類型比對
    # ============================================
    print("\n4. Vx 類型分布比對 (WJ2 + DG3):")
    print("-" * 60)
    
    print("\n   FlowableTaskStats (由 TaskDefinitionKey 判斷):")
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
          AND (TaskBypass != 'Y' OR TaskBypass IS NULL)
        GROUP BY vx ORDER BY cnt DESC
    """)
    flowable_vx = {}
    for row in result.result_rows:
        flowable_vx[row[0]] = row[1]
        print(f"      {row[0]}: {row[1]:,}")
    
    print("\n   Silver 層:")
    result = client.query("""
        SELECT vx_type, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE plant IN ('WJ2', 'DG3') AND is_excluded = 0
        GROUP BY vx_type ORDER BY cnt DESC
    """)
    silver_vx = {}
    for row in result.result_rows:
        silver_vx[row[0]] = row[1]
        print(f"      {row[0]}: {row[1]:,}")
    
    print("\n   Vx 差異:")
    for vx in ['V1', 'V2', 'V3', 'Other']:
        f_cnt = flowable_vx.get(vx, 0)
        s_cnt = silver_vx.get(vx, 0)
        if f_cnt > 0:
            diff = s_cnt - f_cnt
            pct = (diff / f_cnt * 100)
            status = "✅" if abs(pct) < 10 else "⚠️"
            print(f"      {status} {vx}: FlowableTaskStats={f_cnt:,}, Silver={s_cnt:,}, 差異={diff:+,} ({pct:+.1f}%)")

    # ============================================
    # 5. 結論
    # ============================================
    print("\n" + "=" * 80)
    print("5. 驗證結論:")
    print("-" * 80)
    
    total_f = sum(flowable_vx.values())
    total_s = sum(silver_vx.values())
    total_diff = total_s - total_f
    total_pct = (total_diff / total_f * 100) if total_f > 0 else 0
    
    if abs(total_pct) < 10:
        print("   ✅ 資料對齊良好 (差異 < 10%)")
    else:
        print(f"   ⚠️ 資料差異較大 ({total_pct:+.1f}%)，可能原因:")
        print("      - 時間範圍不一致")
        print("      - 過濾條件差異")
        print("      - 資料來源分表")
    
    print("=" * 80)
    client.close()

if __name__ == "__main__":
    main()
