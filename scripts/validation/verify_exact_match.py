#!/usr/bin/env python3
"""
精確驗證腳本：ClickHouse (OR 時間邏輯 + 排除 Bypass)
條件: 2025-12-25, WJ2, NBU, E5
"""
import clickhouse_connect
import os

# ClickHouse Config
CH_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    print("=" * 70)
    print("精確驗證：ClickHouse (OR 時間邏輯 + 排除 Bypass)")
    print("條件: 2025-12-25, WJ2, NBU, E5")
    print("=" * 70)

    # 1. ClickHouse 查詢
    client = clickhouse_connect.get_client(**CH_CONFIG)
    print("\n【ClickHouse】查詢 Silver 層 (模擬 QAS 時間邏輯 + 排除 Bypass)")
    ch_sql = """
        SELECT 
            count() AS total_count,
            countIf(task_status = 'DONE') AS done_count
        FROM silver.mv_fact_task_vx FINAL
        WHERE (task_start_date = '2025-12-25' 
               OR task_claim_date = '2025-12-25' 
               OR task_end_date = '2025-12-25')
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
          AND is_excluded = 0  -- 排除 Bypass
    """
    ch_res = client.query(ch_sql)
    ch_total = ch_res.result_rows[0][0]
    print(f"  SQL: {ch_sql}")
    print(f"  結果: {ch_total} 筆")
    
    print("-" * 30)
    if ch_total == 192:
        print("✅ 驗證成功：數據為 192 筆 (符合預期 198 (QAS) - 6 (Bypass) 的推算)")
    else:
        print(f"⚠️ 驗證結果 {ch_total} 筆 (與預期 192 有出入，需進一步檢查)")

    # 2. 生成 MSSQL 驗證語法建議
    print("\n" + "=" * 70)
    print("建議下一步：請在 QAS DB (MSSQL) 執行以下 SQL 確認 Bypass 數量")
    print("=" * 70)
    print("""
    -- 檢查 2025-12-25 當天的 Bypass (System 自動完成) 數量
    SELECT count(*) 
    FROM ACT_HI_TASKINST T
    JOIN ACT_HI_VARINST V ON T.PROC_INST_ID_ = V.PROC_INST_ID_ AND V.NAME_ = 'autoComplete'
    WHERE ( CAST(T.START_TIME_ AS DATE) = '2025-12-25' OR 
            CAST(T.CLAIM_TIME_ AS DATE) = '2025-12-25' OR 
            CAST(T.END_TIME_ AS DATE) = '2025-12-25' )
      AND V.TEXT_ = '1'
      -- 需加上 Plant/Factory/Line = WJ2/NBU/E5 的關聯條件
    """)

if __name__ == "__main__":
    main()
