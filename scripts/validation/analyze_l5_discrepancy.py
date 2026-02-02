#!/usr/bin/env python3
"""
分析 L5 指標差異：Gold/Silver 層 vs L5_task_sample.sql 邏輯
"""
import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 600,
    "connect_timeout": 30
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("=" * 70)
    print("分析 L5 指標差異：Gold/Silver 層 vs L5_task_sample.sql")
    print("篩選條件: 2025-12-25, WJ2, NBU, E5")
    print("=" * 70)
    
    # 1. 現有 Gold 層結果 (使用 task_create_date)
    print("\n【查詢 1】Gold 層 - 使用 task_create_date (當前邏輯)")
    r1 = client.query("""
        SELECT vx_type, total_task, todo_count, doing_count, done_count
        FROM gold.rmv_l5_task_completion FINAL
        WHERE snapshot_date = '2025-12-25'
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    """)
    print(f"  結果: {r1.result_rows}")
    
    # 2. L5_task_sample.sql 邏輯: START_TIME OR CLAIM_TIME OR END_TIME
    print("\n【查詢 2】模擬 L5_task_sample.sql 邏輯 (任一時間符合即計入)")
    r2 = client.query("""
        SELECT 
            vx_type,
            count() AS total,
            countIf(task_status = 'TODO') AS todo,
            countIf(task_status = 'DOING') AS doing,
            countIf(task_status = 'DONE') AS done
        FROM silver.mv_fact_task_vx FINAL
        WHERE (task_start_date = '2025-12-25' 
               OR task_claim_date = '2025-12-25' 
               OR task_end_date = '2025-12-25')
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
          AND is_excluded = 0
        GROUP BY vx_type
    """)
    print(f"  結果: {r2.result_rows}")
    
    # 3. 比較時間欄位分布
    print("\n【查詢 3】時間欄位分布分析")
    r3 = client.query("""
        SELECT 
            'task_start_date = 2025-12-25' AS condition,
            count() AS cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_start_date = '2025-12-25'
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
          AND is_excluded = 0
        UNION ALL
        SELECT 
            'task_claim_date = 2025-12-25' AS condition,
            count() AS cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_claim_date = '2025-12-25'
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
          AND is_excluded = 0
        UNION ALL
        SELECT 
            'task_end_date = 2025-12-25' AS condition,
            count() AS cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_end_date = '2025-12-25'
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
          AND is_excluded = 0
        UNION ALL
        SELECT 
            'any_date = 2025-12-25 (OR)' AS condition,
            count() AS cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE (task_start_date = '2025-12-25' 
               OR task_claim_date = '2025-12-25' 
               OR task_end_date = '2025-12-25')
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
          AND is_excluded = 0
    """)
    print("  | 條件 | 筆數 |")
    print("  |------|------|")
    for row in r3.result_rows:
        print(f"  | {row[0]} | {row[1]} |")
    
    # 4. 確認資料來源
    print("\n【查詢 4】資料來源確認 - Silver 層使用的是 bpm_act_hi_taskinst")
    r4 = client.query("""
        SELECT count() AS bronze_taskinst_total
        FROM bronze.bpm_act_hi_taskinst FINAL
    """)
    print(f"  bronze.bpm_act_hi_taskinst 總筆數: {r4.result_rows[0][0]:,}")
    
    r5 = client.query("""
        SELECT count() AS bronze_flowable_stats_total
        FROM bronze.common_flowable_task_stats FINAL
    """)
    print(f"  bronze.common_flowable_task_stats 總筆數: {r5.result_rows[0][0]:,}")
    
    print("\n" + "=" * 70)
    print("結論: Gold/Silver 層來源是 bpm_act_hi_taskinst，不是 FlowableTaskStats")
    print("=" * 70)

if __name__ == "__main__":
    main()
