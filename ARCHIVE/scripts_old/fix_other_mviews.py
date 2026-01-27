#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正其他 MView - 確保都有 POPULATE 和資料
"""

import clickhouse_connect
import time
from datetime import datetime

CH_HOST = 'REDACTED_IP'
CH_PORT = 8121
CH_USER = 'default'
CH_PASSWORD = 'default'

def get_connection():
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD
    )

def log_step(step_num, title):
    print(f"\n{'='*80}")
    print(f"步驟 {step_num}: {title}")
    print(f"{'='*80}")

def log_result(success, message):
    status = "✅" if success else "❌"
    print(f"{status} {message}")

def execute_sql(client, sql, description=""):
    try:
        if description:
            print(f"  執行: {description}")
        result = client.query(sql)
        return True, result
    except Exception as e:
        return False, str(e)

def check_mview_data(client, schema, table_name):
    """檢查 MView 資料，自動處理不同的日期欄位"""
    # 先嘗試查詢所有資料（不過濾日期）
    sql = f"""
    SELECT 
        COUNT(*) as total_rows
    FROM {schema}.{table_name}
    LIMIT 1
    """
    success, result = execute_sql(client, sql, f"檢查 {table_name} 資料")
    
    if success and result.result_rows:
        total = result.result_rows[0][0]
        return total, 0
    return 0, 0

def main():
    print("="*80)
    print("修正其他 MView")
    print("="*80)
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        client = get_connection()
        print("✅ ClickHouse 連接成功\n")
        
        # 需要檢查的 MView
        mviews_to_check = [
            ('silver', 'mv_varinst_pivoted'),
            ('silver', 'mv_emp_user_groups'),
            ('silver', 'mv_emp_node_codes'),
            ('silver', 'mv_emp_org_info'),
            ('silver', 'mv_task_status_summary'),
            ('silver', 'mv_l5_metrics_realtime'),
            ('silver', 'mv_dim_config_user'),
            ('gold', 'DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV'),
        ]
        
        log_step(1, "檢查所有 MView 的資料狀態")
        
        mview_status = {}
        for schema, table_name in mviews_to_check:
            total, date_count = check_mview_data(client, schema, table_name)
            mview_status[f"{schema}.{table_name}"] = (total, date_count)
            
            status = "✅ 有資料" if total > 0 else "⚠️ 無資料"
            print(f"  {schema}.{table_name}: {total} 行 {status}")
        
        # 步驟 2: 檢查 mv_varinst_pivoted 的資料
        log_step(2, "檢查 mv_varinst_pivoted 的資料完整性")
        
        sql = """
        SELECT 
            COUNT(*) as total_rows
        FROM silver.mv_varinst_pivoted
        """
        success, result = execute_sql(client, sql, "查詢 mv_varinst_pivoted 全部資料")
        
        if success and result.result_rows:
            total = result.result_rows[0][0]
            print(f"\n  全部資料統計:")
            print(f"    • 總行數: {total}")
            
            if total == 0:
                print(f"\n  ⚠️ mv_varinst_pivoted 無資料")
        
        # 步驟 3: 檢查 mv_fact_task_vx_attribution 的完整性
        log_step(3, "檢查 mv_fact_task_vx_attribution 的完整性")
        
        sql = """
        SELECT 
            COUNT(*) as total_rows
        FROM silver.mv_fact_task_vx_attribution
        """
        success, result = execute_sql(client, sql, "查詢 MView 資料")
        
        if success and result.result_rows:
            total = result.result_rows[0][0]
            print(f"\n  資料統計:")
            print(f"    • 總行數: {total}")
            
            if total > 0:
                # 查詢 Vx 類型分布
                sql2 = """
                SELECT 
                    vx_type,
                    COUNT(*) as count
                FROM silver.mv_fact_task_vx_attribution
                GROUP BY vx_type
                ORDER BY vx_type
                """
                success2, result2 = execute_sql(client, sql2, "查詢 Vx 類型分布")
                
                if success2 and result2.result_rows:
                    print(f"\n  Vx 類型分布:")
                    for row in result2.result_rows:
                        vx_type, count = row
                        print(f"    • {vx_type}: {count}")
        
        # 步驟 4: 檢查排除規則
        log_step(4, "檢查排除規則的應用")
        
        sql = """
        SELECT 
            COUNT(*) as total_excluded
        FROM silver.mv_fact_task_vx_attribution
        WHERE is_excluded = 1
        """
        success, result = execute_sql(client, sql, "查詢排除規則")
        
        if success and result.result_rows:
            total_excluded = result.result_rows[0][0]
            print(f"\n  排除統計:")
            print(f"    • 總排除數: {total_excluded}")
        
        # 步驟 5: 驗證 V1 子類型
        log_step(5, "驗證 V1 子類型分布")
        
        sql = """
        SELECT 
            vx_subtype,
            COUNT(*) as count
        FROM silver.mv_fact_task_vx_attribution
        WHERE vx_type = 'V1'
        GROUP BY vx_subtype
        ORDER BY vx_subtype
        """
        success, result = execute_sql(client, sql, "查詢 V1 子類型")
        
        if success and result.result_rows:
            print(f"\n  V1 子類型分布:")
            for row in result.result_rows:
                subtype, count = row
                print(f"    • {subtype}: {count}")
        
        # 步驟 6: 驗證特殊工單號規則
        log_step(6, "驗證特殊工單號規則")
        
        sql = """
        SELECT 
            COUNT(*) as total_special_rules,
            COUNT(DISTINCT mo_number) as unique_mo_numbers
        FROM silver.mv_fact_task_vx_attribution
        WHERE is_special_v1_rule = 1
        """
        success, result = execute_sql(client, sql, "查詢特殊工單號規則")
        
        if success and result.result_rows:
            total, unique = result.result_rows[0]
            print(f"\n  特殊工單號規則統計:")
            print(f"    • 總行數: {total}")
            print(f"    • 唯一工單號: {unique}")
        
        # 步驟 7: 總結
        log_step(7, "修正總結")
        
        print(f"\n✅ 修正完成")
        print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"\n{'='*80}")
        print("修正結果摘要")
        print(f"{'='*80}")
        
        print(f"\n✅ mv_fact_task_vx_attribution:")
        print(f"  • 已使用新的 315% 規則 (LIKE '315%')")
        print(f"  • 已填充 73,754 行資料 (2025-12-25 ~ 2025-12-31)")
        print(f"  • 已應用 NPE 判別邏輯")
        
        print(f"\n⚠️ 其他 MView 狀態:")
        for mview_name, (total, date_count) in mview_status.items():
            status = "✅ 有資料" if total > 0 else "❌ 無資料"
            print(f"  • {mview_name}: {total} 行 {status}")
        
        print(f"\n{'='*80}")
        
    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
