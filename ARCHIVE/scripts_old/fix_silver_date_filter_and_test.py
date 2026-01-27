#!/usr/bin/env python3
"""
修正 Silver 層日期過濾邏輯並測試
目的：修正 ClickHouse Silver 層與 MSSQL 日期過濾邏輯不一致的問題
"""

import sys
from pathlib import Path

def main():
    print("🔧 Silver 層日期過濾邏輯修正")
    print("=" * 50)
    
    # 檢查修正檔案是否存在
    fixed_sql = Path('sql/12_create_silver_mviews_layer2_fixed.sql')
    test_sql = Path('sql/test_mssql_date_filter_logic.sql')
    
    if not fixed_sql.exists():
        print(f"❌ 修正檔案不存在: {fixed_sql}")
        return False
        
    if not test_sql.exists():
        print(f"❌ 測試檔案不存在: {test_sql}")
        return False
    
    print("✅ 修正檔案已建立")
    print(f"📁 修正檔案: {fixed_sql}")
    print(f"📁 測試檔案: {test_sql}")
    
    print("\n📋 修正內容摘要:")
    print("1. 修正 Silver 層 MVIEW 日期過濾邏輯")
    print("2. 建立與 MSSQL 一致的查詢視圖")
    print("3. 建立測試查詢驗證修正結果")
    
    print("\n🚀 執行步驟:")
    print("1. 執行修正 SQL: sql/12_create_silver_mviews_layer2_fixed.sql")
    print("2. 執行測試 SQL: sql/test_mssql_date_filter_logic.sql")
    print("3. 驗證 WJ2/NBU/E5 2025-12-25 記錄數是否為 5 筆")
    
    print("\n⚠️ 注意事項:")
    print("- 此修正會重建 Silver 層 MVIEW")
    print("- 建議在非生產環境先測試")
    print("- 修正後需要重建 Gold 層 MVIEW")
    
    print("\n📊 預期結果:")
    print("- MSSQL 參考查詢: 5 筆記錄")
    print("- ClickHouse Bronze: 5 筆記錄")
    print("- ClickHouse Silver (修正後): 5 筆記錄")
    print("- ClickHouse Gold (重建後): 正確聚合")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)