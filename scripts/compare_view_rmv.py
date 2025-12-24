import clickhouse_connect
import time

client = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

print("=== View vs RMV 效能比較 ===\n")

# 測試查詢
QUERIES = [
    ("在途任務總數", 
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')"),
    ("TASK_STATUS 分布",
     "SELECT TASK_STATUS, count(*) FROM silver.V_HI_PROC_TASK_NODE GROUP BY TASK_STATUS",
     "SELECT TASK_STATUS, count(*) FROM silver.RMV_HI_PROC_TASK_NODE GROUP BY TASK_STATUS"),
    ("在途任務-依廠區",
     "SELECT PLANT, count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING') GROUP BY PLANT",
     "SELECT PLANT, count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING') GROUP BY PLANT"),
    ("自動完成率",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.RMV_HI_PROC_TASK_NODE"),
]

print("--- 查詢速度比較 ---")
print(f"{'查詢':<20} | {'View (ms)':>10} | {'RMV (ms)':>10} | {'加速比':>8}")
print("-" * 60)

for name, view_sql, rmv_sql in QUERIES:
    # View
    start = time.time()
    client.query(view_sql)
    view_time = (time.time() - start) * 1000
    
    # RMV
    start = time.time()
    client.query(rmv_sql)
    rmv_time = (time.time() - start) * 1000
    
    speedup = view_time / rmv_time if rmv_time > 0 else 0
    print(f"{name:<20} | {view_time:>10.1f} | {rmv_time:>10.1f} | {speedup:>7.1f}x")

# 空間比較
print("\n--- 儲存空間比較 ---")
result = client.query("""
SELECT 
    name,
    formatReadableSize(total_bytes) AS size,
    total_rows
FROM system.tables 
WHERE database = 'silver' 
  AND (name LIKE 'V_%' OR name LIKE 'RMV_%')
ORDER BY name
""")
print(f"{'表名':<35} | {'大小':>12} | {'筆數':>10}")
print("-" * 65)
for row in result.result_rows:
    size = row[1] if row[1] else '0 B (View)'
    rows = row[2] if row[2] else 0
    print(f"{row[0]:<35} | {size:>12} | {rows:>10}")

# RMV 總空間
print("\n--- RMV 總空間 ---")
result = client.query("""
SELECT 
    formatReadableSize(sum(total_bytes)) AS total_size
FROM system.tables 
WHERE database = 'silver' AND name LIKE 'RMV_%'
""")
print(f"RMV 總佔用空間: {result.result_rows[0][0]}")
