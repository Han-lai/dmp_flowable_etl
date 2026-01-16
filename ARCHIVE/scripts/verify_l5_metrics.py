#!/usr/bin/env python3
"""
L5 任務執行完成率驗證腳本
驗證 Silver/Gold 層資料是否正確
"""
import clickhouse_connect

CH_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def main():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    print("=" * 80)
    print("L5 任務執行完成率驗證")
    print("=" * 80)
    
    # 1. Silver 層資料量
    print("\n【1】Silver 層資料量")
    print("-" * 40)
    
    fact_count = client.command("SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION")
    print(f"FACT_TASK_VX_ATTRIBUTION: {fact_count:,} 筆")
    
    # 2. Vx 分布
    print("\n【2】Vx 歸屬分布（排除後）")
    print("-" * 40)
    
    result = client.query("""
        SELECT vx_type, count() as cnt
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE is_excluded = 0
        GROUP BY vx_type
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"  {row[0]}: {row[1]:,}")
    
    # 3. 排除原因分布
    print("\n【3】排除原因分布")
    print("-" * 40)
    
    result = client.query("""
        SELECT exclude_reason, count() as cnt
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE is_excluded = 1
        GROUP BY exclude_reason
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"  {row[0]}: {row[1]:,}")
    
    # 4. V1 子類型分布
    print("\n【4】V1 子類型分布（NPE/MFG）")
    print("-" * 40)
    
    result = client.query("""
        SELECT vx_subtype, count() as cnt
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE vx_type = 'V1' AND is_excluded = 0
        GROUP BY vx_subtype
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        subtype = row[0] if row[0] else 'NULL (一般 V1)'
        print(f"  {subtype}: {row[1]:,}")
    
    # 5. 任務狀態分布
    print("\n【5】任務狀態分布（排除後）")
    print("-" * 40)
    
    result = client.query("""
        SELECT task_status, count() as cnt
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE is_excluded = 0
        GROUP BY task_status
        ORDER BY task_status
    """)
    for row in result.result_rows:
        print(f"  {row[0]}: {row[1]:,}")
    
    # 6. Gold 層快照
    print("\n【6】Gold 層快照資料")
    print("-" * 40)
    
    gold_count = client.command("SELECT count() FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT")
    print(f"DAILY_L5_TASK_COMPLETION_SNAPSHOT: {gold_count:,} 筆")
    
    result = client.query("""
        SELECT snapshot_date, time_period_type, count() as cnt
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
        GROUP BY snapshot_date, time_period_type
        ORDER BY snapshot_date DESC, time_period_type
        LIMIT 10
    """)
    print("\n最近快照:")
    for row in result.result_rows:
        print(f"  {row[0]} / {row[1]}: {row[2]} 筆")
    
    # 7. 範例查詢：V1 任務完成率
    print("\n【7】範例：V1 任務完成率（最新快照）")
    print("-" * 40)
    
    result = client.query("""
        SELECT 
            vx_type,
            vx_subtype,
            time_period_type,
            time_period_value,
            total_task_qty,
            todo_qty,
            doing_qty,
            done_qty,
            done_pct
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
        WHERE vx_type = 'V1'
          AND plant = ''
          AND factory = ''
          AND line = ''
        ORDER BY snapshot_date DESC, time_period_type
        LIMIT 5
    """)
    
    print(f"{'類型':<10} {'子類型':<10} {'區間':<8} {'值':<12} {'總數':<8} {'TODO':<8} {'DOING':<8} {'DONE':<8} {'完成率':<8}")
    print("-" * 90)
    for row in result.result_rows:
        subtype = row[1] if row[1] else '-'
        print(f"{row[0]:<10} {subtype:<10} {row[2]:<8} {row[3]:<12} {row[4]:<8} {row[5]:<8} {row[6]:<8} {row[7]:<8} {row[8]:<8}")
    
    print("\n" + "=" * 80)
    print("驗證完成！")
    print("=" * 80)

if __name__ == "__main__":
    main()
