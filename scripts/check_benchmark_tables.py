import clickhouse_connect

benchmark = clickhouse_connect.get_client(
    host='10.136.218.207', port=8124, 
    username='ch_user', password='ch_strong_password_change_me'
)

print('=== Benchmark 環境表格清單 ===')
result = benchmark.query("""
SELECT database, name, engine 
FROM system.tables 
WHERE database NOT IN ('system', 'INFORMATION_SCHEMA', 'information_schema') 
ORDER BY database, name
""")
for row in result.result_rows:
    print(f'{row[0]}.{row[1]} ({row[2]})')

print('\n=== 各表資料時間範圍 ===')

# 檢查 silver 層
print('\n--- silver 層 ---')
silver_tables = benchmark.query("SELECT name FROM system.tables WHERE database = 'silver'").result_rows
for (table,) in silver_tables:
    try:
        # 嘗試找時間欄位
        cols = benchmark.query(f"SELECT name FROM system.columns WHERE database = 'silver' AND table = '{table}' AND type LIKE '%DateTime%'").result_rows
        if cols:
            time_col = cols[0][0]
            result = benchmark.query(f"SELECT min({time_col}), max({time_col}) FROM silver.{table}")
            print(f'silver.{table} ({time_col}): {result.result_rows[0][0]} ~ {result.result_rows[0][1]}')
        else:
            cnt = benchmark.query(f"SELECT count(*) FROM silver.{table}").result_rows[0][0]
            print(f'silver.{table}: {cnt} 筆 (無時間欄位)')
    except Exception as e:
        print(f'silver.{table}: 錯誤 - {e}')

# 檢查 flowable_analytics 層
print('\n--- flowable_analytics 層 ---')
fa_tables = benchmark.query("SELECT name FROM system.tables WHERE database = 'flowable_analytics'").result_rows
for (table,) in fa_tables:
    try:
        cols = benchmark.query(f"SELECT name FROM system.columns WHERE database = 'flowable_analytics' AND table = '{table}' AND type LIKE '%DateTime%'").result_rows
        if cols:
            time_col = cols[0][0]
            result = benchmark.query(f"SELECT min({time_col}), max({time_col}) FROM flowable_analytics.{table}")
            print(f'flowable_analytics.{table} ({time_col}): {result.result_rows[0][0]} ~ {result.result_rows[0][1]}')
        else:
            cnt = benchmark.query(f"SELECT count(*) FROM flowable_analytics.{table}").result_rows[0][0]
            print(f'flowable_analytics.{table}: {cnt} 筆 (無時間欄位)')
    except Exception as e:
        print(f'flowable_analytics.{table}: 錯誤 - {e}')
