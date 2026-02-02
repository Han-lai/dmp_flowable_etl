#!/usr/bin/env python3
import clickhouse_connect

CLICKHOUSE_CONFIG = {
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default',
    'database': 'default'
}

client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)

# Silver 層
print('SILVER LAYER TABLES:')
print('=' * 80)
try:
    result = client.query('SHOW TABLES FROM silver')
    if result.result_rows:
        for row in result.result_rows:
            table_name = row[0]
            if not table_name.startswith('.inner_id'):
                print(f'  {table_name}')
    else:
        print('  (No tables)')
except Exception as e:
    print(f'  Error: {e}')

print()

# Gold 層
print('GOLD LAYER TABLES:')
print('=' * 80)
try:
    result = client.query('SHOW TABLES FROM gold')
    if result.result_rows:
        for row in result.result_rows:
            table_name = row[0]
            if not table_name.startswith('.inner_id'):
                print(f'  {table_name}')
    else:
        print('  (No tables)')
except Exception as e:
    print(f'  Error: {e}')

print()

# Bronze 所有表
print('BRONZE LAYER - ALL TABLES:')
print('=' * 80)
try:
    result = client.query('SHOW TABLES FROM bronze')
    if result.result_rows:
        bpm_tables = []
        common_tables = []
        other_tables = []
        
        for row in result.result_rows:
            table_name = row[0]
            if table_name.startswith('.inner_id'):
                continue
            elif table_name.startswith('bpm_'):
                bpm_tables.append(table_name)
            elif table_name.startswith('common_'):
                common_tables.append(table_name)
            else:
                other_tables.append(table_name)
        
        if bpm_tables:
            print('  BPM Tables:')
            for t in sorted(bpm_tables):
                print(f'    {t}')
        
        if common_tables:
            print('  Common Tables:')
            for t in sorted(common_tables):
                print(f'    {t}')
        
        if other_tables:
            print('  Other Tables:')
            for t in sorted(other_tables):
                print(f'    {t}')
    else:
        print('  (No tables)')
except Exception as e:
    print(f'  Error: {e}')
