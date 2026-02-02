#!/usr/bin/env python3
"""重置 FlowableTaskStats 失敗批次狀態"""

import clickhouse_connect

client = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

print("🔄 重置失敗批次...")

# 重置失敗批次為 running
reset_sql = """
INSERT INTO bronze.sync_batch_control 
SELECT table_name, batch_id, now64(3), now64(3), watermark_start, watermark_end, 
       'running', 0, 0, '', now64(3), now64(3)
FROM bronze.sync_batch_control FINAL
WHERE table_name = 'FlowableTaskStats' AND status = 'failed'
"""

client.command(reset_sql)
print("✅ 失敗批次已重置")

# 驗證
verify_sql = """
SELECT status, count() 
FROM bronze.sync_batch_control FINAL 
WHERE table_name = 'FlowableTaskStats'
GROUP BY status
"""

result = client.query(verify_sql)
print("\n📊 批次狀態:")
for row in result.result_rows:
    print(f"  {row[0]}: {row[1]} 個")
