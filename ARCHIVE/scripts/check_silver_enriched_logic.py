#!/usr/bin/env python3
"""檢查 silver_enriched_taskinst 的建立邏輯"""

import clickhouse_connect

ext = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print('=== 檢查 silver_enriched_taskinst 的建立邏輯 ===')

# 1. 檢查表的建立語句
print('\n1. 表的建立語句:')
try:
    result = ext.query("SHOW CREATE TABLE silver_enriched_taskinst")
    print(result.result_rows[0][0])
except Exception as e:
    print(f'   錯誤: {e}')

# 2. 檢查是否是物化視圖
print('\n2. 檢查是否是物化視圖:')
try:
    result = ext.query("""
        SELECT engine, create_table_query 
        FROM system.tables 
        WHERE database = 'flowable_analytics' 
        AND name = 'silver_enriched_taskinst'
    """)
    for row in result.result_rows:
        print(f'   Engine: {row[0]}')
        print(f'   Create Query: {row[1][:500]}...')
except Exception as e:
    print(f'   錯誤: {e}')

# 3. 檢查相關的物化視圖
print('\n3. 檢查相關的物化視圖:')
try:
    result = ext.query("""
        SELECT name, engine, create_table_query 
        FROM system.tables 
        WHERE database = 'flowable_analytics' 
        AND engine LIKE '%MaterializedView%'
    """)
    for row in result.result_rows:
        print(f'\n   名稱: {row[0]}')
        print(f'   Engine: {row[1]}')
        print(f'   Query: {row[2][:300]}...')
except Exception as e:
    print(f'   錯誤: {e}')

# 4. 檢查 ACT_HI_TASKINST 原始表
print('\n4. ACT_HI_TASKINST 原始表資料量:')
try:
    result = ext.query("SELECT count() FROM ACT_HI_TASKINST")
    print(f'   筆數: {result.result_rows[0][0]:,}')
except Exception as e:
    print(f'   錯誤: {e}')

# 5. 比較原始表和 silver 表的資料量差異
print('\n5. 比較原始表和 silver 表的資料量:')
try:
    result = ext.query("SELECT count() FROM ACT_HI_TASKINST")
    raw_count = result.result_rows[0][0]
    result = ext.query("SELECT count() FROM silver_enriched_taskinst")
    silver_count = result.result_rows[0][0]
    print(f'   ACT_HI_TASKINST: {raw_count:,}')
    print(f'   silver_enriched_taskinst: {silver_count:,}')
    print(f'   差異: {raw_count - silver_count:,} (被過濾掉的)')
except Exception as e:
    print(f'   錯誤: {e}')

# 6. 檢查 ACT_HI_TASKINST 的 DELETE_REASON_ 分布（可能用於過濾）
print('\n6. ACT_HI_TASKINST 的 DELETE_REASON_ 分布:')
try:
    result = ext.query("""
        SELECT DELETE_REASON_, count() AS cnt
        FROM ACT_HI_TASKINST
        GROUP BY DELETE_REASON_
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(f'   {row[0]}: {row[1]:,}')
except Exception as e:
    print(f'   錯誤: {e}')
