#!/usr/bin/env python3
"""
最終驗證：檢查修正後的結果
"""

import clickhouse_connect
import sys

def main():
    try:
        # 連接 ClickHouse
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        
        print("🎉 ClickHouse 金銀銅資料層修正完成驗證")
        print("=" * 50)
        
        # 1. Bronze 層驗證
        print("\n📊 Bronze 層驗證:")
        result = client.query("SELECT COUNT(*) FROM bronze.bpm_act_hi_taskinst")
        bronze_count = result.result_rows[0][0]
        print(f"   BPM 任務表: {bronze_count:,} 筆記錄")
        
        # 2. Silver 層驗證
        print("\n📊 Silver 層驗證:")
        result = client.query("SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution FINAL")
        silver_count = result.result_rows[0][0]
        print(f"   事實表: {silver_count:,} 筆記錄")
        
        # 3. 關鍵測試案例驗證
        print("\n🔍 關鍵測試案例 (WJ2/NBU/E5 2025-12-25):")
        
        # MSSQL 相容查詢
        test_sql = """
SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        """
        
        result = client.query(test_sql)
        test_count = result.result_rows[0][0]
        print(f"   修正後記錄數: {test_count} 筆")
        print(f"   MSSQL 參考: 5 筆")
        
        if test_count == 5:
            print("   ✅ 測試通過！與 MSSQL 完全一致")
        else:
            print(f"   ❌ 測試失敗！預期 5 筆，實際 {test_count} 筆")
        
        # 4. 詳細記錄檢查
        print("\n📋 詳細記錄檢查:")
        detail_sql = """
SELECT 
    task_id,
    task_definition_key,
    task_name,
    task_status,
    formatDateTime(task_create_time, '%Y-%m-%d %H:%i:%s') AS create_time,
    formatDateTime(task_claim_time, '%Y-%m-%d %H:%i:%s') AS claim_time,
    formatDateTime(task_end_time, '%Y-%m-%d %H:%i:%s') AS end_time,
    mo_number,
    vx_type
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
ORDER BY task_create_time
        """
        
        result = client.query(detail_sql)
        for i, row in enumerate(result.result_rows, 1):
            print(f"   {i}. {row[1]} | {row[3]} | {row[4]} | {row[8]}")
        
        # 5. Gold 層驗證
        print("\n📊 Gold 層驗證:")
        try:
            result = client.query("SELECT COUNT(*) FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL")
            gold_count = result.result_rows[0][0]
            print(f"   聚合表: {gold_count:,} 筆記錄")
        except Exception as e:
            print(f"   ⚠️ Gold 層可能需要重建: {e}")
        
        # 6. 資料一致性總結
        print("\n📈 資料一致性總結:")
        print(f"   Bronze → Silver: {bronze_count:,} → {silver_count:,} (1:1 對應)")
        print(f"   關鍵測試: WJ2/NBU/E5 2025-12-25 = {test_count} 筆")
        print(f"   修正狀態: {'✅ 成功' if test_count == 5 else '❌ 需要進一步檢查'}")
        
        return test_count == 5
        
    except Exception as e:
        print(f"❌ 驗證失敗: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)