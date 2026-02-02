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

print('ACT_HI_PROCINST_0108 Sync Status')
print('=' * 80)

# ClickHouse 筆數
ch_count = client.command('SELECT count(*) FROM bronze.bpm_act_hi_procinst')
print(f'ClickHouse: {ch_count:,} records')

# 批次狀態
completed = client.command('''
SELECT count(*) FROM bronze.sync_batch_control FINAL
WHERE table_name = 'ACT_HI_PROCINST_0108' AND status = 'completed'
''')

running = client.command('''
SELECT count(*) FROM bronze.sync_batch_control FINAL
WHERE table_name = 'ACT_HI_PROCINST_0108' AND status = 'running'
''')

failed = client.command('''
SELECT count(*) FROM bronze.sync_batch_control FINAL
WHERE table_name = 'ACT_HI_PROCINST_0108' AND status = 'failed'
''')

total = completed + running + failed

print()
print('Batch Status:')
print(f'  Completed: {completed}')
print(f'  Running: {running}')
print(f'  Failed: {failed}')
print(f'  Total: {total}')

if total == 0:
    print()
    print('WARNING: No batches found for ACT_HI_PROCINST_0108')
    print('This table may not have been synced yet.')
