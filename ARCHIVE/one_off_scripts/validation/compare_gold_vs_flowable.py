#!/usr/bin/env python3
"""
驗證 Gold 層 vs FlowableTaskStats 資料一致性
比對各層資料是否能產生相符的指標
"""

import clickhouse_connect
from datetime import datetime

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
    print("Bronze → Silver → Gold 層 vs FlowableTaskStats 驗證")
    print("=" * 80)
    print(f"驗證時間: {datetime.now()}")
    
    # ========================================
    # 1. 資料來源總量比對
    # ========================================
    print("\n" + "=" * 80)
    print("1️⃣ 資料來源總量比對")
    print("-" * 80)
    
    # FlowableTaskStats 總量
    flowable_count = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
    """)
    print(f"FlowableTaskStats: {flowable_count:,} 筆")
    
    # Bronze BPM 表總量 (原生 BPM 資料來源)
    bpm_taskinst_count = client.command("""
        SELECT count() FROM bronze.bpm_act_hi_taskinst FINAL
    """)
    print(f"BPM ACT_HI_TASKINST: {bpm_taskinst_count:,} 筆")
    
    # Silver 層總量
    silver_count = client.command("""
        SELECT count() FROM silver.mv_fact_task_vx FINAL
    """)
    print(f"Silver mv_fact_task_vx: {silver_count:,} 筆")
    
    # Gold 層總量 (聚合後)
    gold_total = client.command("""
        SELECT sum(total_task) FROM gold.rmv_l5_task_completion FINAL
    """)
    print(f"Gold rmv_l5_task_completion (sum): {gold_total:,} 筆")
    
    # ========================================
    # 2. TaskStatus 分布比對
    # ========================================
    print("\n" + "=" * 80)
    print("2️⃣ TaskStatus 分布比對")
    print("-" * 80)
    
    # FlowableTaskStats TaskStatus
    print("\n📊 FlowableTaskStats TaskStatus 分布:")
    result = client.query("""
        SELECT TaskStatus, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY TaskStatus
        ORDER BY cnt DESC
    """)
    flowable_status = {row[0]: row[1] for row in result.result_rows}
    for status, cnt in flowable_status.items():
        print(f"  {status}: {cnt:,}")
    
    # Silver 層 task_status
    print("\n📊 Silver mv_fact_task_vx task_status 分布:")
    result = client.query("""
        SELECT task_status, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0
        GROUP BY task_status
        ORDER BY cnt DESC
    """)
    silver_status = {row[0]: row[1] for row in result.result_rows}
    for status, cnt in silver_status.items():
        print(f"  {status}: {cnt:,}")
    
    # Gold 層聚合
    print("\n📊 Gold rmv_l5_task_completion 聚合:")
    result = client.query("""
        SELECT 
            sum(todo_count) as todo,
            sum(doing_count) as doing,
            sum(done_count) as done
        FROM gold.rmv_l5_task_completion FINAL
    """)
    if result.result_rows:
        gold_todo, gold_doing, gold_done = result.result_rows[0]
        print(f"  TODO: {gold_todo:,}")
        print(f"  DOING: {gold_doing:,}")
        print(f"  DONE: {gold_done:,}")
    
    # ========================================
    # 3. Vx 類型分布比對
    # ========================================
    print("\n" + "=" * 80)
    print("3️⃣ Vx 類型分布比對")
    print("-" * 80)
    
    # FlowableTaskStats Vx 分布 (從 TaskDefinitionKey 推導)
    print("\n📊 FlowableTaskStats Vx 分布:")
    result = client.query("""
        SELECT 
            CASE 
                WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
                WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
                WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
                ELSE 'Other'
            END AS vx_type,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY vx_type
        ORDER BY cnt DESC
    """)
    flowable_vx = {row[0]: row[1] for row in result.result_rows}
    for vx, cnt in flowable_vx.items():
        print(f"  {vx}: {cnt:,}")
    
    # Silver 層 Vx 分布
    print("\n📊 Silver mv_fact_task_vx Vx 分布:")
    result = client.query("""
        SELECT vx_type, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0
        GROUP BY vx_type
        ORDER BY cnt DESC
    """)
    silver_vx = {row[0]: row[1] for row in result.result_rows}
    for vx, cnt in silver_vx.items():
        print(f"  {vx}: {cnt:,}")
    
    # Gold 層 Vx 分布
    print("\n📊 Gold rmv_l5_task_completion Vx 分布:")
    result = client.query("""
        SELECT vx_type, sum(total_task) as cnt
        FROM gold.rmv_l5_task_completion FINAL
        GROUP BY vx_type
        ORDER BY cnt DESC
    """)
    gold_vx = {row[0]: row[1] for row in result.result_rows}
    for vx, cnt in gold_vx.items():
        print(f"  {vx}: {cnt:,}")
    
    # ========================================
    # 4. 差異分析
    # ========================================
    print("\n" + "=" * 80)
    print("4️⃣ 差異分析")
    print("-" * 80)
    
    # 計算差異
    diff_total = abs(flowable_count - (gold_total or 0))
    diff_pct = (diff_total / flowable_count * 100) if flowable_count > 0 else 0
    
    print(f"\n總量差異: {diff_total:,} ({diff_pct:.2f}%)")
    
    if diff_pct < 5:
        print("✅ 差異在可接受範圍內 (< 5%)")
    else:
        print("⚠️ 差異較大，需進一步調查")
    
    # 狀態差異
    print("\n狀態差異:")
    for status in ['TODO', 'DOING', 'DONE']:
        f_cnt = flowable_status.get(status, 0)
        s_cnt = silver_status.get(status, 0)
        diff = abs(f_cnt - s_cnt)
        print(f"  {status}: FlowableTaskStats={f_cnt:,}, Silver={s_cnt:,}, 差異={diff:,}")
    
    # ========================================
    # 5. 結論
    # ========================================
    print("\n" + "=" * 80)
    print("5️⃣ 驗證結論")
    print("=" * 80)
    
    if diff_pct < 5 and gold_total and gold_total > 0:
        print("✅ Bronze → Silver → Gold 邏輯能夠產生與 FlowableTaskStats 相符的指標")
        print("   建議持續使用原生 BPM 表作為資料來源")
    else:
        print("⚠️ 存在差異，可能原因：")
        print("   1. 資料來源不同 (BPM 表 vs FlowableTaskStats)")
        print("   2. 過濾條件差異 (is_excluded, TaskBypass)")
        print("   3. 時間範圍不一致")
        print("   4. Vx 歸屬規則差異")
    
    print("\n" + "=" * 80)
    
    client.close()

if __name__ == "__main__":
    main()
