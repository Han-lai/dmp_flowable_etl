#!/usr/bin/env python3
"""
檢查最終修正結果
"""
import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(
        host="10.136.218.207",
        port=8121,
        username="default",
        password="default"
    )
    
    print("檢查修正後的 Gold 層資料...")
    
    # 檢查 WJ2+NBU+E5 2025-12-28 的所有資料
    result = client.query("""
    SELECT 
        vx_type,
        time_period_type,
        time_period_value,
        done_qty
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND snapshot_date = '2025-12-28'
    ORDER BY time_period_type, vx_type
    """)
    
    if result.result_rows:
        print(f"{'VX':<4} {'Period':<8} {'Value':<12} {'Done':<8}")
        print("-" * 35)
        
        v1_done_total = 0
        for row in result.result_rows:
            vx_type, period_type, value, done_qty = row
            if vx_type == 'V1':
                v1_done_total += done_qty
            print(f"{vx_type:<4} {period_type:<8} {value:<12} {done_qty:<8}")
        
        print(f"\n🎯 修正結果:")
        print(f"   V1 Done Tasks 總計: {v1_done_total} 筆")
        print(f"   MSSQL 原始資料: 0 筆")
        print(f"   ✅ 數據一致性: {'通過' if v1_done_total == 0 else '失敗'}")
        
    else:
        print("❌ 無 2025-12-28 資料")
    
    # 檢查整體 V1 任務數變化
    print(f"\n檢查整體 V1 任務數...")
    
    result = client.query("""
    SELECT 
        COUNT(*) as total_v1_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_v1_tasks
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE vx_type = 'V1' AND is_excluded = 0
    """)
    
    if result.result_rows:
        total_v1, done_v1 = result.result_rows[0]
        print(f"   修正後總 V1 任務: {total_v1:,} 筆")
        print(f"   修正後 V1 完成: {done_v1:,} 筆")
        print(f"   修正前總 V1 任務: 436,243 筆 (錯誤)")
        print(f"   ✅ 減少錯誤歸類: {436243 - total_v1:,} 筆")

if __name__ == "__main__":
    main()