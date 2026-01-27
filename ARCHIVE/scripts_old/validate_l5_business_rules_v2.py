#!/usr/bin/env python3
"""
L5 業務規則驗證腳本 - 簡化版

驗證三個核心業務規則：
1. Vx 歸屬規則
2. 排除邏輯
3. 任務狀態計算
"""

import pymssql
import clickhouse_connect
from datetime import datetime
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
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        print("\n【檢查 1.1】工單號 196/199/200/210/212/213/315 開頭的任務是否都被歸類為 V1")
        print("-" * 80)
        
        # ClickHouse 查詢：取得工單號符合規則的任務
        sql = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN vx_type = 'V1' THEN 1 ELSE 0 END) as v1_count,
            SUM(CASE WHEN vx_type != 'V1' THEN 1 ELSE 0 END) as non_v1_count
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE mo_number LIKE '196%' OR mo_number LIKE '199%' 
           OR mo_number LIKE '200%' OR mo_number LIKE '210%'
           OR mo_number LIKE '212%' OR mo_number LIKE '213%'
           OR mo_number LIKE '315%'
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, v1_count, non_v1_count = rows[0]
            print(f"✓ 工單號規則任務總數：{total}")
            print(f"  V1 任務數：{v1_count}")
            print(f"  非 V1 任務數：{non_v1_count}")
            
            if non_v1_count > 0:
                print(f"\n  ⚠️ 發現 {non_v1_count} 筆非 V1 任務，應該都是 V1")
                return False
            else:
                print(f"\n  ✅ 所有工單號規則任務都被正確歸類為 V1")
        
        print("\n【檢查 1.2】其他任務是否按 TaskDefinitionKey 前兩碼正確歸類")
        print("-" * 80)
        
        # 查詢不符合工單號規則的任務
        sql = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN vx_type = SUBSTRING(task_definition_key, 1, 2) THEN 1 ELSE 0 END) as correct,
            SUM(CASE WHEN vx_type != SUBSTRING(task_definition_key, 1, 2) THEN 1 ELSE 0 END) as incorrect
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE (mo_number NOT LIKE '196%' AND mo_number NOT LIKE '199%' 
               AND mo_number NOT LIKE '200%' AND mo_number NOT LIKE '210%'
               AND mo_number NOT LIKE '212%' AND mo_number NOT LIKE '213%'
               AND mo_number NOT LIKE '315%')
           OR mo_number IS NULL
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, correct, incorrect = rows[0]
            print(f"✓ 非工單號規則任務總數：{total}")
            print(f"  符合規則：{correct}")
            print(f"  不符合規則：{incorrect}")
            
            if incorrect > 0:
                print(f"\n  ⚠️ 發現 {incorrect} 筆不符合規則的任務")
                return False
            else:
                print(f"\n  ✅ 所有任務都按 TaskDefinitionKey 前兩碼正確歸類")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 驗證失敗：{str(e)}")
        return False


# ============================================================================
# 2. 排除邏輯驗證
# ============================================================================

def validate_exclusion_logic():
    """驗證排除邏輯"""
    print("\n" + "="*80)
    print("【規則 2】排除邏輯驗證")
    print("="*80)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
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
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, excluded, not_excluded = rows[0]
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
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, excluded, not_excluded = rows[0]
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
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, excluded, not_excluded = rows[0]
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
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, included, excluded = rows[0]
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
        
    except Exception as e:
        print(f"\n❌ 驗證失敗：{str(e)}")
        return False


# ============================================================================
# 3. 任務狀態計算驗證
# ============================================================================

def validate_task_status():
    """驗證任務狀態計算"""
    print("\n" + "="*80)
    print("【規則 3】任務狀態計算驗證")
    print("="*80)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        print("\n【檢查 3.1】三種狀態任務數加總驗證")
        print("-" * 80)
        
        sql = """
        SELECT 
            COUNT(*) as total_tasks,
            SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_count,
            SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_count,
            SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_count
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, todo, doing, done = rows[0]
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
        
        print("\n【檢查 3.2】各狀態任務分布")
        print("-" * 80)
        
        sql = """
        SELECT 
            task_status,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM silver.FACT_TASK_VX_ATTRIBUTION), 2) as percentage
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        GROUP BY task_status
        ORDER BY task_status
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        for status, count, pct in rows:
            print(f"  {status}: {count} 筆 ({pct}%)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 驗證失敗：{str(e)}")
        return False


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
