#!/usr/bin/env python3
"""
查詢 Gold 層 L5 任務完成率
"""
import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 600,  # 增加超時時間到 10 分鐘
    "connect_timeout": 30
}

def main():
    print("正在連接 ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 從 Gold 層查詢
    print("=== Gold 層查詢: rmv_l5_task_completion ===")
    print("篩選條件: snapshot_date=2025-12-25, plant=WJ2, factory=NBU, line=E5")
    print()
    
    result = client.query("""
        SELECT 
            snapshot_date,
            vx_type,
            region, plant, factory, line,
            total_task,
            todo_count,
            doing_count,
            done_count,
            completion_rate,
            execution_rate
        FROM gold.rmv_l5_task_completion FINAL
        WHERE snapshot_date = '2025-12-25'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
        ORDER BY vx_type
    """)
    
    if result.result_rows:
        print("| Date | Vx | Region | Plant | Factory | Line | Total | TODO | DOING | DONE | 完成率 | 執行率 |")
        print("|------|-----|--------|-------|---------|------|------:|-----:|------:|-----:|-------:|-------:|")
        for row in result.result_rows:
            print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]} | {row[9]} | {row[10]}% | {row[11]}% |")
    else:
        print("Gold 層查無資料")
    
    # 檢查 Silver 層資料
    print()
    print("=== Silver 層驗證: mv_fact_task_vx ===")
    result2 = client.query("""
        SELECT 
            vx_type,
            count() AS total,
            countIf(task_status = 'TODO') AS todo,
            countIf(task_status = 'DOING') AS doing,
            countIf(task_status = 'DONE') AS done
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_create_date = '2025-12-25'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND is_excluded = 0
        GROUP BY vx_type
        ORDER BY vx_type
    """)
    
    if result2.result_rows:
        print("| Vx | Total | TODO | DOING | DONE |")
        print("|----|------:|-----:|------:|-----:|")
        for row in result2.result_rows:
            print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |")
    else:
        print("Silver 層查無資料")

if __name__ == "__main__":
    main()
