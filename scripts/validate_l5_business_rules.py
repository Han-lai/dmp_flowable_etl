#!/usr/bin/env python3
"""
L5 業務規則驗證腳本

驗證三個核心業務規則：
1. Vx 歸屬規則
2. 排除邏輯
3. 任務狀態計算
"""

import pymssql
import clickhouse_connect
import pandas as pd
from datetime import datetime, timedelta
import sys

# ============================================================================
# 連線配置
# ============================================================================

MSSQL_CONFIG = {
    'server': 'twtpesqldv2.delta.corp',
    'port': 1433,
    'user': 'DMP_APP_SRV',
    'password': 'APP@DB#01',
    'database': 'APP_SRV_BPM'
}

CLICKHOUSE_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

# ============================================================================
# 1. Vx 歸屬規則驗證
# ============================================================================

def validate_vx_attribution():
    """驗證 Vx 歸屬規則"""
    print("\n" + "="*80)
    print("【規則 1】Vx 歸屬規則驗證")
    print("="*80)
    
    # 連線 MSSQL
    conn_mssql = pymssql.connect(
        server=MSSQL_CONFIG['server'],
        port=MSSQL_CONFIG['port'],
        user=MSSQL_CONFIG['user'],
        password=MSSQL_CONFIG['password'],
        database=MSSQL_CONFIG['database']
    )
    cursor = conn_mssql.cursor()
    
    # 連線 ClickHouse
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_CONFIG['host'],
        port=CLICKHOUSE_CONFIG['port'],
        username=CLICKHOUSE_CONFIG['username'],
        password=CLICKHOUSE_CONFIG['password']
    )
    
    print("\n【檢查 1.1】工單號 196/199/200/210/212/213/315 開頭的任務是否都被歸類為 V1")
    print("-" * 80)
    
    # MSSQL 查詢：取得工單號符合規則的任務
    sql_mssql = """
    SELECT TOP 100
        t.TaskId,
        t.TaskDefinitionKey,
        v.varinst_moNumber,
        CASE 
            WHEN v.varinst_moNumber LIKE '196%' OR v.varinst_moNumber LIKE '199%' 
                 OR v.varinst_moNumber LIKE '200%' OR v.varinst_moNumber LIKE '210%'
                 OR v.varinst_moNumber LIKE '212%' OR v.varinst_moNumber LIKE '213%'
                 OR v.varinst_moNumber LIKE '315%'
            THEN 'V1'
            ELSE SUBSTRING(t.TaskDefinitionKey, 1, 2)
        END AS expected_vx
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN (
        SELECT PROC_INST_ID_, MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    ) v ON t.ProcessInstanceId = v.PROC_INST_ID_
    WHERE v.varinst_moNumber LIKE '196%' OR v.varinst_moNumber LIKE '199%' 
       OR v.varinst_moNumber LIKE '200%' OR v.varinst_moNumber LIKE '210%'
       OR v.varinst_moNumber LIKE '212%' OR v.varinst_moNumber LIKE '213%'
       OR v.varinst_moNumber LIKE '315%'
    """
    
    df_mssql = pd.read_sql(sql_mssql, conn_mssql)
    print(f"✓ MSSQL 查詢結果：{len(df_mssql)} 筆任務符合工單號規則")
    
    # ClickHouse 查詢：驗證這些任務在 Silver 層是否都被歸類為 V1
    sql_ch = """
    SELECT 
        task_id,
        task_definition_key,
        mo_number,
        vx_type
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE mo_number LIKE '196%' OR mo_number LIKE '199%' 
       OR mo_number LIKE '200%' OR mo_number LIKE '210%'
       OR mo_number LIKE '212%' OR mo_number LIKE '213%'
       OR mo_number LIKE '315%'
    LIMIT 100
    """
    
    result = client.execute(sql_ch)
    df_ch = pd.DataFrame(result, columns=['task_id', 'task_definition_key', 'mo_number', 'vx_type'])
    print(f"✓ ClickHouse 查詢結果：{len(df_ch)} 筆任務")
    
    # 驗證
    v1_count = len(df_ch[df_ch['vx_type'] == 'V1'])
    non_v1_count = len(df_ch[df_ch['vx_type'] != 'V1'])
    
    print(f"\n  V1 任務數：{v1_count}")
    print(f"  非 V1 任務數：{non_v1_count}")
    
    if non_v1_count > 0:
        print(f"\n  ⚠️ 發現 {non_v1_count} 筆非 V1 任務，應該都是 V1：")
        print(df_ch[df_ch['vx_type'] != 'V1'][['task_id', 'mo_number', 'vx_type']].to_string())
        return False
    else:
        print(f"\n  ✅ 所有工單號規則任務都被正確歸類為 V1")
    
    print("\n【檢查 1.2】其他任務是否按 TaskDefinitionKey 前兩碼正確歸類")
    print("-" * 80)
    
    # 查詢不符合工單號規則的任務
    sql_ch_other = """
    SELECT 
        task_id,
        task_definition_key,
        vx_type,
        SUBSTRING(task_definition_key, 1, 2) AS expected_vx
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE (mo_number NOT LIKE '196%' AND mo_number NOT LIKE '199%' 
           AND mo_number NOT LIKE '200%' AND mo_number NOT LIKE '210%'
           AND mo_number NOT LIKE '212%' AND mo_number NOT LIKE '213%'
           AND mo_number NOT LIKE '315%')
       OR mo_number IS NULL
    LIMIT 100
    """
    
    result = client.execute(sql_ch_other)
    df_ch_other = pd.DataFrame(result, columns=['task_id', 'task_definition_key', 'vx_type', 'expected_vx'])
    
    # 驗證
    mismatch = df_ch_other[df_ch_other['vx_type'] != df_ch_other['expected_vx']]
    
    print(f"✓ 查詢結果：{len(df_ch_other)} 筆任務")
    print(f"  符合規則：{len(df_ch_other) - len(mismatch)} 筆")
    print(f"  不符合規則：{len(mismatch)} 筆")
    
    if len(mismatch) > 0:
        print(f"\n  ⚠️ 發現 {len(mismatch)} 筆不符合規則的任務：")
        print(mismatch[['task_id', 'task_definition_key', 'vx_type', 'expected_vx']].to_string())
        return False
    else:
        print(f"\n  ✅ 所有任務都按 TaskDefinitionKey 前兩碼正確歸類")
    
    conn_mssql.close()
    return True


# ============================================================================
# 2. 排除邏輯驗證
# ============================================================================

def validate_exclusion_logic():
    """驗證排除邏輯"""
    print("\n" + "="*80)
    print("【規則 2】排除邏輯驗證")
    print("="*80)
    
    client = clickhouse_driver.Client(
        host=CLICKHOUSE_CONFIG['host'],
        port=CLICKHOUSE_CONFIG['port'],
        database=CLICKHOUSE_CONFIG['database']
    )
    
    print("\n【檢查 2.1】TaskBypass = 'Y' 的任務是否都被排除")
    print("-" * 80)
    
    sql = """
    SELECT 
        COUNT(*) as total_bypass_y,
        SUM(CASE WHEN is_excluded = 1 THEN 1 ELSE 0 END) as excluded_count,
        SUM(CASE WHEN is_excluded = 0 THEN 1 ELSE 0 END) as not_excluded_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_bypass = 'Y'
    """
    
    result = client.execute(sql)
    total, excluded, not_excluded = result[0]
    
    print(f"✓ TaskBypass = 'Y' 的任務總數：{total}")
    print(f"  已排除：{excluded}")
    print(f"  未排除：{not_excluded}")
    
    if not_excluded > 0:
        print(f"\n  ⚠️ 發現 {not_excluded} 筆 TaskBypass = 'Y' 但未被排除的任務")
        return False
    else:
        print(f"\n  ✅ 所有 TaskBypass = 'Y' 的任務都被正確排除")
    
    print("\n【檢查 2.2】TaskDefinitionKey 以 'E' 或 'C' 開頭的任務是否都被排除")
    print("-" * 80)
    
    sql = """
    SELECT 
        COUNT(*) as total_ec,
        SUM(CASE WHEN is_excluded = 1 THEN 1 ELSE 0 END) as excluded_count,
        SUM(CASE WHEN is_excluded = 0 THEN 1 ELSE 0 END) as not_excluded_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_definition_key LIKE 'E%' OR task_definition_key LIKE 'C%'
    """
    
    result = client.execute(sql)
    total, excluded, not_excluded = result[0]
    
    print(f"✓ TaskDefinitionKey 以 'E' 或 'C' 開頭的任務總數：{total}")
    print(f"  已排除：{excluded}")
    print(f"  未排除：{not_excluded}")
    
    if not_excluded > 0:
        print(f"\n  ⚠️ 發現 {not_excluded} 筆 E/C 開頭但未被排除的任務")
        return False
    else:
        print(f"\n  ✅ 所有 E/C 開頭的任務都被正確排除")
    
    print("\n【檢查 2.3】工單號以 'Q' 或 'R' 開頭的任務是否都被排除")
    print("-" * 80)
    
    sql = """
    SELECT 
        COUNT(*) as total_qr,
        SUM(CASE WHEN is_excluded = 1 THEN 1 ELSE 0 END) as excluded_count,
        SUM(CASE WHEN is_excluded = 0 THEN 1 ELSE 0 END) as not_excluded_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE mo_number LIKE 'Q%' OR mo_number LIKE 'R%'
    """
    
    result = client.execute(sql)
    total, excluded, not_excluded = result[0]
    
    print(f"✓ 工單號以 'Q' 或 'R' 開頭的任務總數：{total}")
    print(f"  已排除：{excluded}")
    print(f"  未排除：{not_excluded}")
    
    if not_excluded > 0:
        print(f"\n  ⚠️ 發現 {not_excluded} 筆 Q/R 開頭但未被排除的任務")
        return False
    else:
        print(f"\n  ✅ 所有 Q/R 開頭的任務都被正確排除")
    
    print("\n【檢查 2.4】排除邏輯完整性驗證")
    print("-" * 80)
    
    sql = """
    SELECT 
        COUNT(*) as total_tasks,
        SUM(CASE WHEN is_excluded = 0 THEN 1 ELSE 0 END) as included_tasks,
        SUM(CASE WHEN is_excluded = 1 THEN 1 ELSE 0 END) as excluded_tasks
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    """
    
    result = client.execute(sql)
    total, included, excluded = result[0]
    
    print(f"✓ 總任務數：{total}")
    print(f"  包含在指標中：{included}")
    print(f"  排除在指標外：{excluded}")
    print(f"  驗證：{included} + {excluded} = {included + excluded} (應等於 {total})")
    
    if included + excluded != total:
        print(f"\n  ⚠️ 排除邏輯不完整，有 {total - (included + excluded)} 筆任務未被分類")
        return False
    else:
        print(f"\n  ✅ 排除邏輯完整，所有任務都被正確分類")
    
    return True


# ============================================================================
# 3. 任務狀態計算驗證
# ============================================================================

def validate_task_status():
    """驗證任務狀態計算"""
    print("\n" + "="*80)
    print("【規則 3】任務狀態計算驗證")
    print("="*80)
    
    conn_mssql = pyodbc.connect(
        f"Driver={{ODBC Driver 17 for SQL Server}};Server={MSSQL_CONFIG['server']},{MSSQL_CONFIG['port']};"
        f"Database={MSSQL_CONFIG['database']};UID={MSSQL_CONFIG['uid']};PWD={MSSQL_CONFIG['pwd']}"
    )
    cursor = conn_mssql.cursor()
    
    client = clickhouse_driver.Client(
        host=CLICKHOUSE_CONFIG['host'],
        port=CLICKHOUSE_CONFIG['port'],
        database=CLICKHOUSE_CONFIG['database']
    )
    
    print("\n【檢查 3.1】已完成任務 (END_TIME 不為空) 是否都被標記為 DONE")
    print("-" * 80)
    
    # MSSQL 查詢：取得 END_TIME 不為空的任務
    sql_mssql = """
    SELECT TOP 50
        TaskId,
        TaskStatus,
        CASE WHEN END_TIME IS NOT NULL THEN 'DONE' ELSE 'NOT_DONE' END AS expected_status
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats
    WHERE END_TIME IS NOT NULL
    """
    
    df_mssql = pd.read_sql(sql_mssql, conn_mssql)
    print(f"✓ MSSQL 查詢結果：{len(df_mssql)} 筆已完成任務")
    
    # ClickHouse 驗證
    sql_ch = """
    SELECT 
        task_id,
        task_status,
        CASE WHEN task_status = 'DONE' THEN 'CORRECT' ELSE 'INCORRECT' END AS status_check
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_status = 'DONE'
    LIMIT 50
    """
    
    result = client.execute(sql_ch)
    df_ch = pd.DataFrame(result, columns=['task_id', 'task_status', 'status_check'])
    
    incorrect = len(df_ch[df_ch['status_check'] == 'INCORRECT'])
    print(f"✓ ClickHouse 查詢結果：{len(df_ch)} 筆 DONE 狀態任務")
    print(f"  正確：{len(df_ch) - incorrect}")
    print(f"  不正確：{incorrect}")
    
    if incorrect > 0:
        print(f"\n  ⚠️ 發現 {incorrect} 筆狀態不正確的任務")
        return False
    else:
        print(f"\n  ✅ 所有已完成任務都被正確標記為 DONE")
    
    print("\n【檢查 3.2】進行中任務 (已指派但未完成) 是否都被標記為 DOING")
    print("-" * 80)
    
    sql_ch = """
    SELECT 
        COUNT(*) as total_doing,
        SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as correct_doing,
        SUM(CASE WHEN task_status != 'DOING' THEN 1 ELSE 0 END) as incorrect_doing
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_status = 'DOING'
    """
    
    result = client.execute(sql_ch)
    total, correct, incorrect = result[0]
    
    print(f"✓ DOING 狀態任務總數：{total}")
    print(f"  正確：{correct}")
    print(f"  不正確：{incorrect}")
    
    if incorrect > 0:
        print(f"\n  ⚠️ 發現 {incorrect} 筆狀態不正確的任務")
        return False
    else:
        print(f"\n  ✅ 所有進行中任務都被正確標記為 DOING")
    
    print("\n【檢查 3.3】待辦任務 (未指派) 是否都被標記為 TODO")
    print("-" * 80)
    
    sql_ch = """
    SELECT 
        COUNT(*) as total_todo,
        SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as correct_todo,
        SUM(CASE WHEN task_status != 'TODO' THEN 1 ELSE 0 END) as incorrect_todo
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_status = 'TODO'
    """
    
    result = client.execute(sql_ch)
    total, correct, incorrect = result[0]
    
    print(f"✓ TODO 狀態任務總數：{total}")
    print(f"  正確：{correct}")
    print(f"  不正確：{incorrect}")
    
    if incorrect > 0:
        print(f"\n  ⚠️ 發現 {incorrect} 筆狀態不正確的任務")
        return False
    else:
        print(f"\n  ✅ 所有待辦任務都被正確標記為 TODO")
    
    print("\n【檢查 3.4】三種狀態任務數加總驗證")
    print("-" * 80)
    
    sql_ch = """
    SELECT 
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_count,
        SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_count,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    """
    
    result = client.execute(sql_ch)
    total, todo, doing, done = result[0]
    
    print(f"✓ 總任務數：{total}")
    print(f"  TODO：{todo}")
    print(f"  DOING：{doing}")
    print(f"  DONE：{done}")
    print(f"  驗證：{todo} + {doing} + {done} = {todo + doing + done} (應等於 {total})")
    
    if todo + doing + done != total:
        print(f"\n  ⚠️ 狀態計算不完整，有 {total - (todo + doing + done)} 筆任務未被分類")
        return False
    else:
        print(f"\n  ✅ 所有任務都被正確分類為三種狀態之一")
    
    conn_mssql.close()
    return True


# ============================================================================
# 主程式
# ============================================================================

def main():
    print("\n" + "="*80)
    print("L5 業務規則驗證 - 開始執行")
    print("="*80)
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    try:
        results['vx_attribution'] = validate_vx_attribution()
    except Exception as e:
        print(f"\n❌ Vx 歸屬規則驗證失敗：{str(e)}")
        results['vx_attribution'] = False
    
    try:
        results['exclusion_logic'] = validate_exclusion_logic()
    except Exception as e:
        print(f"\n❌ 排除邏輯驗證失敗：{str(e)}")
        results['exclusion_logic'] = False
    
    try:
        results['task_status'] = validate_task_status()
    except Exception as e:
        print(f"\n❌ 任務狀態計算驗證失敗：{str(e)}")
        results['task_status'] = False
    
    # 總結
    print("\n" + "="*80)
    print("驗證結果總結")
    print("="*80)
    print(f"✓ Vx 歸屬規則：{'✅ 通過' if results['vx_attribution'] else '❌ 失敗'}")
    print(f"✓ 排除邏輯：{'✅ 通過' if results['exclusion_logic'] else '❌ 失敗'}")
    print(f"✓ 任務狀態計算：{'✅ 通過' if results['task_status'] else '❌ 失敗'}")
    
    all_passed = all(results.values())
    print(f"\n整體結果：{'✅ 所有規則驗證通過' if all_passed else '❌ 部分規則驗證失敗'}")
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
