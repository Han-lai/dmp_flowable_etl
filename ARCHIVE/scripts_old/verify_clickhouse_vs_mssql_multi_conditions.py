#!/usr/bin/env python3
"""
對帳驗證：ClickHouse vs MSSQL - 多組條件驗證
基於既有的 verify_clickhouse_vs_mssql.py 邏輯，支援參數化條件
"""
import pymssql
import clickhouse_connect
from datetime import datetime

def verify_condition(date, task_bypass, plant, line, condition_name):
    """
    執行單組條件的驗證
    """
    print("=" * 100)
    print(f"對帳驗證：{condition_name}")
    print(f"條件: date={date}, taskBypass='{task_bypass}', plant='{plant}', line='{line}'")
    print("=" * 100)

    # MSSQL 連線
    mssql_conn = pymssql.connect(
        server='twtpesqldv2.delta.corp',
        port='1433',
        user='DMP_APP_SRV',
        password='APP@DB#01',
        database='APP_SRV_BPM'
    )
    mssql_cursor = mssql_conn.cursor()

    # ClickHouse 連線
    ch_client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )

    # ============================================
    # 1. MSSQL Reference SQL
    # ============================================
    print("\n" + "=" * 50)
    print("1. MSSQL Reference SQL 結果")
    print("=" * 50)

    mssql_cursor.execute(f"""
    SELECT * FROM (
    SELECT
        hti.ID_ AS taskId,
        CASE
            WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
            WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
            ELSE 'TODO'
        END AS taskStatus,
        CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END AS taskBypass,
        var_plant.TEXT_ AS plant,
        var_lineName.TEXT_ AS line,
        var_factory.TEXT_ AS factory,
        CONVERT(VARCHAR, hti.START_TIME_, 120) AS taskCreateTime
    FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
    INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
    ) AS t
    WHERE t.taskCreateTime BETWEEN '{date} 00:00:00' AND '{date} 23:59:59'
      AND taskBypass='{task_bypass}' 
      AND plant='{plant}' 
      AND line='{line}'
    ORDER BY taskId
    """)

    mssql_rows = mssql_cursor.fetchall()
    mssql_task_ids = set()
    mssql_status_counts = {}

    print(f"\n總筆數: {len(mssql_rows)}")
    if len(mssql_rows) <= 10:  # 只顯示前10筆
        print(f"\n{'taskId':<40} {'status':<8} {'bypass':<6} {'plant':<6} {'line':<6}")
        print("-" * 80)
        for row in mssql_rows:
            task_id = row[0]
            status = row[1]
            mssql_task_ids.add(task_id)
            mssql_status_counts[status] = mssql_status_counts.get(status, 0) + 1
            print(f"{task_id:<40} {status:<8} {row[2]:<6} {row[3]:<6} {row[4]:<6}")
    else:
        for row in mssql_rows:
            task_id = row[0]
            status = row[1]
            mssql_task_ids.add(task_id)
            mssql_status_counts[status] = mssql_status_counts.get(status, 0) + 1

    print("\n狀態統計:")
    for status, count in sorted(mssql_status_counts.items()):
        print(f"  {status}: {count}")

    # ============================================
    # 2. ClickHouse Silver 層結果
    # ============================================
    print("\n" + "=" * 50)
    print("2. ClickHouse Silver 層結果")
    print("=" * 50)

    ch_result = ch_client.query(f"""
    SELECT 
        task_id,
        task_status,
        task_bypass,
        plant,
        line
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE task_create_date = '{date}'
      AND task_bypass = '{task_bypass}'
      AND plant = '{plant}'
      AND line = '{line}'
    ORDER BY task_id
    """)

    ch_task_ids = set()
    ch_status_counts = {}

    print(f"\n總筆數: {len(ch_result.result_rows)}")
    if len(ch_result.result_rows) <= 10:  # 只顯示前10筆
        print(f"\n{'taskId':<40} {'status':<8} {'bypass':<6} {'plant':<6} {'line':<6}")
        print("-" * 80)
        for row in ch_result.result_rows:
            task_id = row[0]
            status = row[1]
            ch_task_ids.add(task_id)
            ch_status_counts[status] = ch_status_counts.get(status, 0) + 1
            print(f"{task_id:<40} {status:<8} {row[2]:<6} {str(row[3]):<6} {str(row[4]):<6}")
    else:
        for row in ch_result.result_rows:
            task_id = row[0]
            status = row[1]
            ch_task_ids.add(task_id)
            ch_status_counts[status] = ch_status_counts.get(status, 0) + 1

    print("\n狀態統計:")
    for status, count in sorted(ch_status_counts.items()):
        print(f"  {status}: {count}")

    # ============================================
    # 3. 對帳結果
    # ============================================
    print("\n" + "=" * 100)
    print("3. 對帳結果")
    print("=" * 100)

    # 筆數比較
    print(f"\n筆數比較:")
    print(f"  MSSQL:      {len(mssql_rows)}")
    print(f"  ClickHouse: {len(ch_result.result_rows)}")
    print(f"  差異:       {len(mssql_rows) - len(ch_result.result_rows)}")

    # TaskId 比較
    only_in_mssql = mssql_task_ids - ch_task_ids
    only_in_ch = ch_task_ids - mssql_task_ids

    print(f"\nTaskId 比較:")
    print(f"  只在 MSSQL:      {len(only_in_mssql)}")
    print(f"  只在 ClickHouse: {len(only_in_ch)}")

    if only_in_mssql and len(only_in_mssql) <= 5:
        print(f"  MSSQL 獨有: {only_in_mssql}")
    if only_in_ch and len(only_in_ch) <= 5:
        print(f"  ClickHouse 獨有: {only_in_ch}")

    # 狀態分布比較
    print(f"\n狀態分布比較:")
    all_statuses = set(mssql_status_counts.keys()) | set(ch_status_counts.keys())
    status_match = True
    for status in sorted(all_statuses):
        mssql_cnt = mssql_status_counts.get(status, 0)
        ch_cnt = ch_status_counts.get(status, 0)
        match = "✓" if mssql_cnt == ch_cnt else "✗"
        if mssql_cnt != ch_cnt:
            status_match = False
        print(f"  {status}: MSSQL={mssql_cnt}, ClickHouse={ch_cnt} {match}")

    # 最終結論
    print("\n" + "=" * 100)
    is_pass = (len(mssql_rows) == len(ch_result.result_rows) and 
               not only_in_mssql and not only_in_ch and status_match)
    
    if is_pass:
        print("✅ 對帳通過！MSSQL 與 ClickHouse 結果完全一致")
        result = "PASS"
    else:
        print("⚠️ 對帳失敗！請檢查差異")
        result = "FAIL"
    print("=" * 100)

    mssql_conn.close()
    
    return {
        'condition': condition_name,
        'date': date,
        'task_bypass': task_bypass,
        'plant': plant,
        'line': line,
        'result': result,
        'mssql_count': len(mssql_rows),
        'clickhouse_count': len(ch_result.result_rows),
        'difference': len(mssql_rows) - len(ch_result.result_rows)
    }

def main():
    """
    執行多組條件驗證
    """
    print("MSSQL vs ClickHouse 多組條件驗證")
    print("基於既有驗證邏輯，測試不同條件組合")
    print("=" * 100)
    
    # 定義測試條件組合
    test_conditions = [
        # 原始條件
        {
            'date': '2025-12-31',
            'task_bypass': 'N',
            'plant': 'WJ2',
            'line': 'E5',
            'name': '條件1: 原始條件 (WJ2-E5, 2025-12-31)'
        },
        # 不同日期
        {
            'date': '2025-12-30',
            'task_bypass': 'N',
            'plant': 'WJ2',
            'line': 'E5',
            'name': '條件2: 前一天 (WJ2-E5, 2025-12-30)'
        },
        # 不同產線
        {
            'date': '2025-12-31',
            'task_bypass': 'N',
            'plant': 'WJ2',
            'line': 'E6',
            'name': '條件3: 不同產線 (WJ2-E6, 2025-12-31)'
        },
        # 不同廠區
        {
            'date': '2025-12-31',
            'task_bypass': 'N',
            'plant': 'WJ1',
            'line': 'E5',
            'name': '條件4: 不同廠區 (WJ1-E5, 2025-12-31)'
        },
        # 包含 Bypass
        {
            'date': '2025-12-31',
            'task_bypass': 'Y',
            'plant': 'WJ2',
            'line': 'E5',
            'name': '條件5: 包含Bypass (WJ2-E5, bypass=Y)'
        }
    ]
    
    results = []
    
    # 執行每組驗證
    for i, condition in enumerate(test_conditions, 1):
        print(f"\n開始執行第 {i} 組驗證...")
        try:
            result = verify_condition(
                condition['date'],
                condition['task_bypass'],
                condition['plant'],
                condition['line'],
                condition['name']
            )
            results.append(result)
        except Exception as e:
            print(f"❌ 第 {i} 組驗證執行失敗: {e}")
            results.append({
                'condition': condition['name'],
                'result': 'ERROR',
                'error': str(e)
            })
        
        print(f"\n第 {i} 組驗證完成\n")
    
    # ============================================
    # 總結報告
    # ============================================
    print("\n" + "=" * 100)
    print("多組條件驗證總結報告")
    print("=" * 100)
    
    print(f"\n{'條件':<50} {'結果':<8} {'MSSQL筆數':<10} {'CH筆數':<10} {'差異':<8}")
    print("-" * 100)
    
    pass_count = 0
    fail_count = 0
    error_count = 0
    
    for result in results:
        if result['result'] == 'PASS':
            pass_count += 1
            print(f"{result['condition']:<50} {'✅PASS':<8} {result['mssql_count']:<10} {result['clickhouse_count']:<10} {result['difference']:<8}")
        elif result['result'] == 'FAIL':
            fail_count += 1
            print(f"{result['condition']:<50} {'⚠️FAIL':<8} {result['mssql_count']:<10} {result['clickhouse_count']:<10} {result['difference']:<8}")
        else:
            error_count += 1
            print(f"{result['condition']:<50} {'❌ERROR':<8} {'N/A':<10} {'N/A':<10} {'N/A':<8}")
    
    print("\n" + "=" * 100)
    print("最終統計:")
    print(f"  ✅ 通過: {pass_count}")
    print(f"  ⚠️ 失敗: {fail_count}")
    print(f"  ❌ 錯誤: {error_count}")
    print(f"  📊 總計: {len(results)}")
    
    if pass_count == len(results):
        print("\n🎉 所有條件驗證均通過！MSSQL 與 ClickHouse 資料一致性良好")
    elif fail_count > 0:
        print(f"\n⚠️ 有 {fail_count} 組條件驗證失敗，需要檢查資料一致性問題")
    
    print("=" * 100)

if __name__ == "__main__":
    main()