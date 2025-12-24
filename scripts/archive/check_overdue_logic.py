import clickhouse_connect

# 參考環境
client = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print("=== 檢查參考環境的逾期判斷邏輯 ===\n")

# 1. 列出所有 View，找有 overdue/due/delay 相關的
print("--- 1. 搜尋含有 overdue/due/delay 關鍵字的 View ---")
result = client.query("SHOW TABLES")
views = [row[0] for row in result.result_rows]
print(f"總共 {len(views)} 個表/View:")
for v in views:
    print(f"  - {v}")

# 2. 檢查 silver_enriched_taskinst 是否有 due_date 欄位
print("\n--- 2. 檢查 silver_enriched_taskinst 的 due_date 使用 ---")
result = client.query("""
SELECT 
    due_date IS NOT NULL AS has_due,
    count(*) AS cnt
FROM silver_enriched_taskinst
GROUP BY has_due
""")
for row in result.result_rows:
    status = "有 due_date" if row[0] else "無 due_date"
    print(f"{status}: {row[1]} 筆")

# 3. 檢查有 due_date 的任務
print("\n--- 3. 有 due_date 的任務範例 ---")
result = client.query("""
SELECT task_id, task_name, due_date, start_time, end_time, task_state
FROM silver_enriched_taskinst
WHERE due_date IS NOT NULL
LIMIT 5
""")
for row in result.result_rows:
    print(f"  {row[0][:20]}... | {row[1]} | due: {row[2]} | state: {row[5]}")

# 4. 搜尋所有 View 定義中是否有 overdue 相關邏輯
print("\n--- 4. 搜尋 View 定義中的 overdue/delay 邏輯 ---")
for view in views:
    try:
        result = client.query(f"SHOW CREATE VIEW flowable_analytics.{view}")
        definition = result.result_rows[0][0].lower()
        if 'overdue' in definition or 'delay' in definition or 'due_date' in definition:
            print(f"\n[{view}] 包含相關邏輯:")
            # 找出相關行
            lines = result.result_rows[0][0].split('\n')
            for line in lines:
                if 'overdue' in line.lower() or 'delay' in line.lower() or 'due_date' in line.lower():
                    print(f"    {line.strip()[:100]}")
    except:
        pass

# 5. 檢查是否有 HealthSettings 或類似的設定表
print("\n--- 5. 搜尋設定相關的表 ---")
for table in views:
    if 'setting' in table.lower() or 'config' in table.lower() or 'health' in table.lower():
        print(f"  找到: {table}")

# 6. 檢查 gold 層是否有逾期相關的彙總
print("\n--- 6. 檢查 gold 層的欄位 ---")
gold_views = [v for v in views if 'gold' in v.lower()]
for gv in gold_views:
    try:
        result = client.query(f"DESCRIBE {gv}")
        cols = [row[0] for row in result.result_rows]
        overdue_cols = [c for c in cols if 'overdue' in c.lower() or 'delay' in c.lower() or 'due' in c.lower()]
        if overdue_cols:
            print(f"\n[{gv}] 逾期相關欄位: {overdue_cols}")
    except:
        pass
