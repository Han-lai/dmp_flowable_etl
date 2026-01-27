#!/usr/bin/env python3
"""
執行 ClickHouse MVIEW 重建腳本
"""

import clickhouse_connect
import sys
from pathlib import Path

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
        
        # 讀取重建 SQL
        sql_file = Path('sql/REBUILD_ALL_MVIEWS.sql')
        if not sql_file.exists():
            print(f"❌ SQL 檔案不存在: {sql_file}")
            return False
            
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print(f"📖 讀取 SQL 檔案: {sql_file}")
        
        # 分割 SQL 語句（以分號分隔）
        sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        print(f"🔧 準備執行 {len(sql_statements)} 個 SQL 語句")
        
        # 逐一執行 SQL 語句
        for i, sql in enumerate(sql_statements, 1):
            if sql.startswith('--') or not sql:
                continue
                
            try:
                print(f"⏳ 執行語句 {i}/{len(sql_statements)}: {sql[:50]}...")
                
                # 執行 SQL
                if sql.upper().startswith('SELECT'):
                    result = client.query(sql)
                    print(f"   📊 查詢結果: {result.result_rows}")
                    if result.result_rows:
                        for row in result.result_rows:
                            print(f"   📋 {row}")
                else:
                    client.command(sql)
                    print(f"   ✅ 執行成功")
                    
            except Exception as e:
                print(f"   ❌ 執行失敗: {e}")
                continue
        
        print("\n🎉 MVIEW 重建完成")
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