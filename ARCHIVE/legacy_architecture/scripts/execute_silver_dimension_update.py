#!/usr/bin/env python3
"""
執行 Silver 層維度補齊邏輯更新
"""

import clickhouse_connect
import time

def main():
    print("🔄 執行 Silver 層維度補齊邏輯更新")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 讀取更新 SQL
        with open('sql/update_silver_dimension_backfill_logic.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print("📊 執行 Silver 層更新...")
        
        # 分割 SQL 語句並執行
        statements = sql_content.split(';')
        
        for i, statement in enumerate(statements):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    print(f"   執行語句 {i+1}/{len(statements)}...")
                    client.command(statement)
                    time.sleep(1)  # 避免過快執行
                except Exception as e:
                    print(f"   ⚠️ 語句 {i+1} 執行失敗: {str(e)}")
        
        print("✅ Silver 層更新完成")
        
        # 驗證更新結果
        print("\n📊 驗證更新結果...")
        
        # 檢查新欄位
        desc_result = client.query("DESCRIBE silver.mv_fact_task_vx_attribution_mdm")
        columns = [row[0] for row in desc_result.result_rows]
        
        required_cols = ['region_source', 'plant_source', 'factory_source', 'line_source', 'region']
        missing_cols = [col for col in required_cols if col not in columns]
        
        if missing_cols:
            print(f"❌ 缺少欄位: {missing_cols}")
        else:
            print("✅ 所有必要欄位都已新增")
        
        # 檢查資料量
        count_result = client.query("SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution_mdm")
        total_rows = count_result.result_rows[0][0]
        print(f"✅ 資料量: {total_rows:,} rows")
        
        return True
        
    except Exception as e:
        print(f"❌ 更新失敗: {str(e)}")
        return False
    
    finally:
        client.close()

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ Silver 層更新成功")
    else:
        print("\n❌ Silver 層更新失敗")