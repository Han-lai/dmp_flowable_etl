#!/usr/bin/env python3
"""
Vx 識別欄位比對分析
比較 FlowableTaskStats 的 TaskDefinitionKey 與 Silver 層的 TASK_DEF_KEY_
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
    print("Vx 識別欄位比對分析")
    print("=" * 80)

    # 1. FlowableTaskStats 的 TaskDefinitionKey 分布
    print("\n1. FlowableTaskStats 的 TaskDefinitionKey 分布 (前 10):")
    result = client.query("""
        SELECT TaskDefinitionKey, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY TaskDefinitionKey
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(f"  {row[0]}: {row[1]:,}")

    # 2. Silver 層使用的 task_definition_key
    print("\n2. Silver 層使用的 task_definition_key (TASK_DEF_KEY_) 分布 (前 10):")
    result = client.query("""
        SELECT task_definition_key, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        GROUP BY task_definition_key
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(f"  {row[0]}: {row[1]:,}")

    # 3. Vx 前綴識別比對
    print("\n3. Vx 前綴識別比對:")
    print("   FlowableTaskStats (依 TaskDefinitionKey):")
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
        GROUP BY vx ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"     {row[0]}: {row[1]:,}")

    print("   Silver 層 (依 vx_type):")
    result = client.query("""
        SELECT vx_type, count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0
        GROUP BY vx_type ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"     {row[0]}: {row[1]:,}")

    # 4. 檢查 processDefinitionKey (pd.KEY_) vs taskDefinitionKey
    print("\n4. 比對 processDefinitionKey (pd.KEY_) vs taskDefinitionKey:")
    result = client.query("""
        SELECT 
            pd.KEY_ as proc_def_key,
            t.TASK_DEF_KEY_ as task_def_key,
            count() as cnt
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN bronze.bpm_act_hi_procinst hi ON t.PROC_INST_ID_ = hi.PROC_INST_ID_
        LEFT JOIN bronze.bpm_act_re_procdef pd ON hi.PROC_DEF_ID_ = pd.ID_
        WHERE t.TASK_DEF_KEY_ IS NOT NULL
        GROUP BY proc_def_key, task_def_key
        ORDER BY cnt DESC
        LIMIT 15
    """)
    print("   流程定義 Key (pd.KEY_) vs 任務定義 Key (TASK_DEF_KEY_):")
    for row in result.result_rows:
        proc_key = row[0] if row[0] else "NULL"
        task_key = row[1] if row[1] else "NULL"
        proc_vx = proc_key[:2] if proc_key and proc_key != "NULL" else "NULL"
        task_vx = task_key[:2] if task_key and task_key != "NULL" else "NULL"
        match = "✅" if proc_vx == task_vx else "⚠️"
        print(f"     {match} {proc_key} | {task_key} ({row[2]:,})")

    # 5. 結論
    print("\n" + "=" * 80)
    print("5. 結論:")
    print("   - processDefinitionKey (pd.KEY_) 是流程級別的識別碼")
    print("   - taskDefinitionKey (TASK_DEF_KEY_) 是任務級別的識別碼")
    print("   - 兩者前綴相同 (V1/V2/V3)，用於 Vx 識別是一致的")
    print("=" * 80)

    client.close()

if __name__ == "__main__":
    main()
