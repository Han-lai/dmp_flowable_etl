#!/usr/bin/env python3
"""
重新生成 2025-12-31 Gold 層快照
使用修正後的 Silver 層資料
"""
import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(
        host="REDACTED_IP",
        port=8121,
        username="default",
        password="default"
    )
    
    print("重新生成 2025-12-31 Gold 層快照...")
    
    # 1. 刪除 2025-12-31 的錯誤快照
    delete_sql = """
    ALTER TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT 
    DELETE WHERE snapshot_date = '2025-12-31'
    """
    client.command(delete_sql)
    print("✅ 刪除 2025-12-31 錯誤快照")
    
    # 2. 重新生成快照
    regenerate_sql = """
    INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    SELECT 
        '2025-12-31' AS snapshot_date,
        vx_type,
        vx_subtype,
        plant,
        factory,
        line,
        'day' AS time_period_type,
        '2025-12-31' AS time_period_value,
        COUNT(*) AS total_task_qty,
        SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) AS todo_qty,
        SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) AS doing_qty,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) AS done_qty,
        SUM(CASE WHEN task_status IN ('DOING', 'DONE') THEN 1 ELSE 0 END) AS doing_done_qty,
        SUM(CASE WHEN task_status IN ('TODO', 'DOING') THEN 1 ELSE 0 END) AS todo_doing_acc_qty,
        CASE 
            WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))
            ELSE 0 
        END AS todo_pct,
        CASE 
            WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))
            ELSE 0 
        END AS doing_pct,
        CASE 
            WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))
            ELSE 0 
        END AS done_pct,
        CASE 
            WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN task_status IN ('DOING', 'DONE') THEN 1 ELSE 0 END) * 100.0 / COUNT(*))
            ELSE 0 
        END AS doing_done_pct,
        1 AS _version,
        now64(3) AS _snapshot_time
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE task_create_date = '2025-12-31'
      AND is_excluded = 0
    GROUP BY vx_type, vx_subtype, plant, factory, line
    HAVING COUNT(*) > 0
    """
    client.command(regenerate_sql)
    print("✅ 重新生成 2025-12-31 日度快照")
    
    # 3. 驗證結果
    verify_sql = """
    SELECT 
        vx_type,
        plant,
        factory,
        line,
        total_task_qty,
        done_qty,
        done_pct
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-31'
      AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND time_period_type = 'day'
    ORDER BY vx_type
    """
    
    result = client.query(verify_sql)
    if result.result_rows:
        print("\n✅ 驗證結果 - WJ2+NBU+E5 2025-12-31:")
        print(f"{'VX':<4} {'Plant':<6} {'Factory':<8} {'Line':<8} {'Total':<6} {'Done':<6} {'%':<6}")
        print("-" * 50)
        
        for row in result.result_rows:
            vx_type, plant, factory, line, total, done, pct = row
            print(f"{vx_type:<4} {plant:<6} {factory:<8} {line:<8} {total:<6} {done:<6} {pct:<6.1f}")
        
        print(f"\n🎉 修正成功！Gold 層快照已更新")
    else:
        print("❌ 無 2025-12-31 資料")

if __name__ == "__main__":
    main()