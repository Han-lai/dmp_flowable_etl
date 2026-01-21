#!/usr/bin/env python3
"""
檢查 V1 + CNE + WJ2 + NBU + E5 + 2025-12-31 的任務數量
"""

import clickhouse_connect
from datetime import datetime

CLICKHOUSE_CONFIG = {
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def check_v1_cne_tasks():
    """檢查 V1 CNE 任務數量"""
    print("\n" + "="*100)
    print("【檢查】V1 + CNE + WJ2 + NBU + E5 + 2025-12-31 任務數量")
    print("="*100)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        # 查詢 V1 CNE 任務
        sql = """
        SELECT 
            vx_type,
            vx_subtype,
            task_status,
            COUNT(*) AS task_count
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE vx_type = 'V1'
          AND vx_subtype = 'V1_NPE'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND toDate(task_create_time) = '2025-12-31'
          AND is_excluded = 0
        GROUP BY vx_type, vx_subtype, task_status
        ORDER BY task_status
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        print("\n【結果】V1_NPE (CNE) 任務統計")
        print("-" * 100)
        
        todo_count = 0
        doing_count = 0
        done_count = 0
        
        for vx_type, vx_subtype, task_status, task_count in rows:
            print(f"Vx: {vx_type}, SubType: {vx_subtype}, Status: {task_status}, Count: {task_count}")
            if task_status == 'TODO':
                todo_count = task_count
            elif task_status == 'DOING':
                doing_count = task_count
            elif task_status == 'DONE':
                done_count = task_count
        
        total = todo_count + doing_count + done_count
        
        print("\n【統計摘要】")
        print("-" * 100)
        print(f"TODO:  {todo_count} 筆")
        print(f"DOING: {doing_count} 筆")
        print(f"DONE:  {done_count} 筆")
        print(f"小計:  {total} 筆")
        
        # 檢查是否符合預期
        print("\n【預期值對比】")
        print("-" * 100)
        print(f"預期 TODO:  9 筆 | 實際: {todo_count} 筆 | {'✅' if todo_count == 9 else '❌'}")
        print(f"預期 DOING: 2 筆 | 實際: {doing_count} 筆 | {'✅' if doing_count == 2 else '❌'}")
        print(f"預期 DONE:  1 筆 | 實際: {done_count} 筆 | {'✅' if done_count == 1 else '❌'}")
        print(f"預期 小計:  12 筆 | 實際: {total} 筆 | {'✅' if total == 12 else '❌'}")
        
        # 如果不符合，查詢詳細資訊
        if total != 12 or todo_count != 9 or doing_count != 2 or done_count != 1:
            print("\n【診斷】數據不符合預期，查詢詳細資訊...")
            print("-" * 100)
            
            # 查詢所有 V1 任務
            sql_all_v1 = """
            SELECT 
                vx_type,
                vx_subtype,
                COUNT(*) AS task_count
            FROM silver.mv_fact_task_vx_attribution FINAL
            WHERE vx_type = 'V1'
              AND plant = 'WJ2' 
              AND factory = 'NBU' 
              AND line = 'E5'
              AND toDate(task_create_time) = '2025-12-31'
              AND is_excluded = 0
            GROUP BY vx_type, vx_subtype
            """
            
            result = client.query(sql_all_v1)
            rows = result.result_rows
            
            print("\nWJ2+NBU+E5+2025-12-31 的所有 V1 任務：")
            for vx_type, vx_subtype, task_count in rows:
                print(f"  {vx_type} / {vx_subtype}: {task_count} 筆")
            
            # 查詢所有任務（不限制 Vx）
            sql_all = """
            SELECT 
                vx_type,
                COUNT(*) AS task_count
            FROM silver.mv_fact_task_vx_attribution FINAL
            WHERE plant = 'WJ2' 
              AND factory = 'NBU' 
              AND line = 'E5'
              AND toDate(task_create_time) = '2025-12-31'
              AND is_excluded = 0
            GROUP BY vx_type
            ORDER BY vx_type
            """
            
            result = client.query(sql_all)
            rows = result.result_rows
            
            print("\nWJ2+NBU+E5+2025-12-31 的所有任務（按 Vx 類型）：")
            for vx_type, task_count in rows:
                print(f"  {vx_type}: {task_count} 筆")
        
        print("\n" + "="*100)
        
    except Exception as e:
        print(f"\n❌ 查詢失敗：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    check_v1_cne_tasks()
