#!/usr/bin/env python3
"""
直接檢查 Gold 層日期狀況
"""
import clickhouse_connect

def check():
    client = clickhouse_connect.get_client(
        host="REDACTED_IP",
        port=8121,
        username="default",
        password="default"
    )
    
    # 檢查 Gold 層所有日期
    sql = """
    SELECT DISTINCT snapshot_date
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE snapshot_date >= '2025-12-01'
    ORDER BY snapshot_date
    """
    
    result = client.query(sql)
    print("Gold 層現有日期:")
    for row in result.result_rows:
        print(f"  {row[0]}")
    
    print(f"\n總共: {len(result.result_rows)} 個日期")

if __name__ == "__main__":
    check()