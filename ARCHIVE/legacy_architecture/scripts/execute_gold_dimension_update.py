#!/usr/bin/env python3
"""
執行 Gold 層維度補齊邏輯更新
"""

import clickhouse_connect
import time

def main():
    print("🔄 執行 Gold 層維度補齊邏輯更新")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 讀取 SQL 檔案
        with open('sql/update_gold_dimension_backfill_logic.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割 SQL 語句
        sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
        
        print(f"📋 準備執行 {len(sql_statements)} 個 SQL 語句")
        
        for i, sql in enumerate(sql_statements, 1):
            if not sql or sql.isspace():
                continue
                
            print(f"\n🔄 執行語句 {i}/{len(sql_statements)}")
            print(f"📝 SQL: {sql[:100]}...")
            
            try:
                start_time = time.time()
                result = client.command(sql)
                end_time = time.time()
                
                print(f"✅ 執行成功 (耗時: {end_time - start_time:.2f}s)")
                
                # 如果是 SELECT 語句，顯示結果
                if sql.strip().upper().startswith('SELECT'):
                    if hasattr(result, 'result_rows') and result.result_rows:
                        for row in result.result_rows[:5]:  # 只顯示前5行
                            print(f"   {row}")
                    elif isinstance(result, list) and result:
                        for row in result[:5]:
                            print(f"   {row}")
                
            except Exception as e:
                print(f"❌ 執行失敗: {str(e)}")
                if "already exists" not in str(e).lower():
                    raise
        
        print(f"\n✅ Gold 層維度補齊邏輯更新完成")
        return True
        
    except Exception as e:
        print(f"❌ 更新失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        client.close()

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n🎉 Gold 層更新成功")
    else:
        print(f"\n💥 Gold 層更新失敗")