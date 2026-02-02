#!/usr/bin/env python3
"""
檢查 Other 類別和 Plant 缺失原因
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
    print("檢查 'Other' 類別和 Plant 缺失原因")
    print("=" * 80)

    # 1. FlowableTaskStats 中 "Other" 類別的 TaskDefinitionKey
    print("\n1. FlowableTaskStats 中 'Other' 類別的 TaskDefinitionKey:")
    result = client.query("""
        SELECT TaskDefinitionKey, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE TaskDefinitionKey NOT LIKE 'V1%'
          AND TaskDefinitionKey NOT LIKE 'V2%'
          AND TaskDefinitionKey NOT LIKE 'V3%'
        GROUP BY TaskDefinitionKey
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"     {row[0]}: {row[1]:,}")

    # 2. Silver 層中這些 TaskDefinitionKey 是否被過濾
    print("\n2. Silver 層對這些 Key 的處理:")
    result = client.query("""
        SELECT task_definition_key, is_excluded, exclude_reason, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_definition_key NOT LIKE 'V1%'
          AND task_definition_key NOT LIKE 'V2%'
          AND task_definition_key NOT LIKE 'V3%'
        GROUP BY task_definition_key, is_excluded, exclude_reason
        ORDER BY cnt DESC
        LIMIT 20
    """)
    for row in result.result_rows:
        print(f"     {row[0]} | is_excluded={row[1]} | reason={row[2]} | {row[3]:,}")

    # 3. Bronze BPM 表中各 Plant 分布
    print("\n3. Bronze 層 (bpm_act_hi_taskinst) 中 Plant 資料確認:")
    print("   (透過 VARINST 關聯取得 plant)")
    result = client.query("""
        SELECT v.varinst_plant as plant, count() as cnt
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        GROUP BY plant
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(f"     {row[0]}: {row[1]:,}")

    # 4. 確認 DET6, DG2, WG1 在 Bronze VARINST 中是否存在
    print("\n4. 確認 DET6, DG2, WG1 在 VARINST 中是否存在:")
    for plant in ['DET6', 'DG2', 'WG1']:
        count = client.command(f"""
            SELECT count() FROM silver.mv_varinst_pivoted
            WHERE varinst_plant = '{plant}'
        """)
        print(f"     {plant}: {count:,}")

    # 5. FlowableTaskStats 中 DET6/DG2/WG1 的 ProcessDefinitionKey
    print("\n5. FlowableTaskStats 中 DET6/DG2/WG1 的 ProcessDefinitionKey:")
    result = client.query("""
        SELECT Plant, ProcessDefinitionKey, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant IN ('DET6', 'DG2', 'WG1')
        GROUP BY Plant, ProcessDefinitionKey
        ORDER BY Plant, cnt DESC
    """)
    for row in result.result_rows:
        print(f"     {row[0]} | {row[1]}: {row[2]:,}")

    # 6. 結論
    print("\n" + "=" * 80)
    print("6. 結論:")
    print("-" * 80)
    print("   'Other' 類別可能包含 E%, C% 等被 Silver 層排除的流程")
    print("   DET6, DG2, WG1 等 Plant 可能是:")
    print("     - 不在 BPM 表的資料範圍內")
    print("     - 或來自不同的資料來源/分表")
    print("=" * 80)

    client.close()

if __name__ == "__main__":
    main()
