#!/usr/bin/env python3
"""
檢查 WJ2+NBU+E5 在 2025-12-28, 2025-12-30, 2025-12-31 的 TODO/DOING/DONE 任務數量
"""

import clickhouse_connect
from datetime import datetime

CLICKHOUSE_CONFIG = {
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def check_task_counts():
    """檢查任務數量"""
    print("\n" + "="*100)
    print("【檢查】WJ2+NBU+E5 任務數量 (2025-12-28, 2025-12-30, 2025-12-31)")
    print("="*100)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        # 查詢三個日期的任務數量
        sql = """
        SELECT 
            toDate(task_create_time) AS snapshot_date,
            task_status,
            COUNT(*) AS task_count
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND toDate(task_create_time) IN ('2025-12-28', '2025-12-30', '2025-12-31')
          AND is_excluded = 0
        GROUP BY snapshot_date, task_status
        ORDER BY snapshot_date, task_status
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        print("\n【結果】WJ2+NBU+E5 任務統計（未排除）")
        print("-" * 100)
        print(f"{'日期':<15} {'狀態':<10} {'任務數':<15}")
        print("-" * 100)
        
        # 按日期分組顯示
        current_date = None
        date_totals = {}
        
        for snapshot_date, task_status, task_count in rows:
            if snapshot_date != current_date:
                if current_date is not None:
                    total = date_totals.get(current_date, 0)
                    print(f"{str(current_date):<15} {'小計':<10} {total:<15}")
                    print("-" * 100)
                current_date = snapshot_date
                date_totals[snapshot_date] = 0
            
            print(f"{str(snapshot_date):<15} {task_status:<10} {task_count:<15}")
            date_totals[snapshot_date] = date_totals.get(snapshot_date, 0) + task_count
        
        # 最後一個日期的小計
        if current_date is not None:
            total = date_totals.get(current_date, 0)
            print(f"{str(current_date):<15} {'小計':<10} {total:<15}")
        
        print("-" * 100)
        
        # 詳細統計（按狀態）
        print("\n【詳細統計 - 按狀態】")
        print("-" * 100)
        
        for date_str in ['2025-12-28', '2025-12-30', '2025-12-31']:
            sql_detail = f"""
            SELECT 
                task_status,
                COUNT(*) AS task_count
            FROM silver.mv_fact_task_vx_attribution FINAL
            WHERE plant = 'WJ2' 
              AND factory = 'NBU' 
              AND line = 'E5'
              AND toDate(task_create_time) = '{date_str}'
              AND is_excluded = 0
            GROUP BY task_status
            ORDER BY task_status
            """
            
            result = client.query(sql_detail)
            rows = result.result_rows
            
            todo_count = 0
            doing_count = 0
            done_count = 0
            
            for task_status, task_count in rows:
                if task_status == 'TODO':
                    todo_count = task_count
                elif task_status == 'DOING':
                    doing_count = task_count
                elif task_status == 'DONE':
                    done_count = task_count
            
            total = todo_count + doing_count + done_count
            
            print(f"\n{date_str}:")
            print(f"  TODO:  {todo_count:>10} 筆")
            print(f"  DOING: {doing_count:>10} 筆")
            print(f"  DONE:  {done_count:>10} 筆")
            print(f"  小計:  {total:>10} 筆")
        
        # Vx 類型統計
        print("\n【詳細統計 - 按 Vx 類型】")
        print("-" * 100)
        
        for date_str in ['2025-12-28', '2025-12-30', '2025-12-31']:
            sql_vx = f"""
            SELECT 
                vx_type,
                COUNT(*) AS task_count
            FROM silver.mv_fact_task_vx_attribution FINAL
            WHERE plant = 'WJ2' 
              AND factory = 'NBU' 
              AND line = 'E5'
              AND toDate(task_create_time) = '{date_str}'
              AND is_excluded = 0
            GROUP BY vx_type
            ORDER BY vx_type
            """
            
            result = client.query(sql_vx)
            rows = result.result_rows
            
            print(f"\n{date_str}:")
            total_vx = 0
            for vx_type, task_count in rows:
                print(f"  {vx_type:<10}: {task_count:>10} 筆")
                total_vx += task_count
            print(f"  {'小計':<10}: {total_vx:>10} 筆")
        
        # Vx 類型 + 狀態交叉統計
        print("\n【詳細統計 - Vx 類型 × 狀態】")
        print("-" * 100)
        
        for date_str in ['2025-12-28', '2025-12-30', '2025-12-31']:
            sql_cross = f"""
            SELECT 
                vx_type,
                task_status,
                COUNT(*) AS task_count
            FROM silver.mv_fact_task_vx_attribution FINAL
            WHERE plant = 'WJ2' 
              AND factory = 'NBU' 
              AND line = 'E5'
              AND toDate(task_create_time) = '{date_str}'
              AND is_excluded = 0
            GROUP BY vx_type, task_status
            ORDER BY vx_type, task_status
            """
            
            result = client.query(sql_cross)
            rows = result.result_rows
            
            print(f"\n{date_str}:")
            print(f"  {'Vx':<10} {'狀態':<10} {'數量':<10}")
            print(f"  {'-'*30}")
            
            for vx_type, task_status, task_count in rows:
                print(f"  {vx_type:<10} {task_status:<10} {task_count:>10} 筆")
        
        print("\n" + "="*100)
        
    except Exception as e:
        print(f"\n❌ 查詢失敗：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    check_task_counts()
