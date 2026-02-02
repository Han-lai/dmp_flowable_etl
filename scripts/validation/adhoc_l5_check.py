import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\n查詢條件: Plant='WJ2', Factory='NBU', Line='E4'")
    print("日期範圍: 2025-12-25 ~ 2025-12-27")
    
    query = """
    SELECT 
        snapshot_date,
        vx_type,
        total_task,
        todo_count,
        doing_count,
        done_count,
        completion_rate,
        execution_rate
    FROM gold.rmv_l5_task_completion FINAL
    WHERE 
        plant = 'WJ2' 
        AND factory = 'NBU' 
        AND line = 'E4'
        AND snapshot_date IN ('2025-12-25', '2025-12-26', '2025-12-27')
    ORDER BY snapshot_date, vx_type
    """
    
    result = client.query(query)
    
    if result.result_rows:
        print("\n| Date | Vx | Total | TODO | DOING | DONE | 完成率 | 執行率 |")
        print("|------|----|------:|-----:|------:|-----:|-------:|-------:|")
        for row in result.result_rows:
            print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]}% | {row[7]}% |")
    else:
        print("\n❌ 查無資料")

if __name__ == "__main__":
    main()
