#!/usr/bin/env python3
"""
檢查 Silver 層 MVIEW 依賴的表是否存在
"""

import clickhouse_connect
import sys

def main():
    try:
        # 連接 ClickHouse
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default'
        )
        
        print("✅ 連接 ClickHouse 成功")
        
        # 檢查依賴的表
        dependencies = [
            'bronze.bmp_act_hi_varinst',
            'bronze.bpm_act_hi_taskinst',
            'bronze.bpm_act_hi_procinst',
            'bronze.common_hr_employee',
            'silver.mv_varinst_pivoted'
        ]
        
        print("\n🔍 檢查依賴表:")
        for table in dependencies:
            try:
                result = client.query(f"SELECT COUNT(*) FROM {table} LIMIT 1")
                count = result.result_rows[0][0] if result.result_rows else 0
                print(f"   ✅ {table}: {count} 筆記錄")
            except Exception as e:
                print(f"   ❌ {table}: 不存在或無法訪問 - {e}")
        
        # 檢查 Silver 資料庫是否存在
        print("\n🔍 檢查 Silver 資料庫:")
        try:
            result = client.query("SHOW DATABASES")
            databases = [row[0] for row in result.result_rows]
            if 'silver' in databases:
                print("   ✅ silver 資料庫存在")
            else:
                print("   ❌ silver 資料庫不存在")
                
            # 檢查 Silver 資料庫中的表
            result = client.query("SHOW TABLES FROM silver")
            tables = [row[0] for row in result.result_rows]
            print(f"   📋 Silver 資料庫中的表: {tables}")
            
        except Exception as e:
            print(f"   ❌ 檢查 Silver 資料庫失敗: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)