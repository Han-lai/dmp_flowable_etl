"""查詢 ACT_HI_VARINST 表中的 moNumber 變數"""
import clickhouse_connect

client = clickhouse_connect.get_client(
    host="10.136.218.207",
    port=8121,
    username="default",
    password="default"
)

# 查詢 moNumber 變數範例
print("=== moNumber 變數範例 ===")
result = client.query("""
    SELECT DISTINCT TEXT_ 
    FROM bronze.bpm_act_hi_varinst 
    WHERE NAME_ = 'moNumber' 
    AND TEXT_ IS NOT NULL
    LIMIT 30
""")
for row in result.result_rows:
    print(f"  {row[0]}")

# 查詢 196/199/200/210/212/213/315 開頭的 moNumber
print("\n=== 196/199/200/210/212/213/315 開頭的 moNumber ===")
result = client.query("""
    SELECT DISTINCT TEXT_ 
    FROM bronze.bpm_act_hi_varinst 
    WHERE NAME_ = 'moNumber' 
    AND (TEXT_ LIKE '196%' OR TEXT_ LIKE '199%' OR TEXT_ LIKE '200%' 
         OR TEXT_ LIKE '210%' OR TEXT_ LIKE '212%' OR TEXT_ LIKE '213%' OR TEXT_ LIKE '315%')
    LIMIT 20
""")
for row in result.result_rows:
    print(f"  {row[0]}")

# 查詢 Q 開頭的 moNumber
print("\n=== Q 開頭的 moNumber ===")
result = client.query("""
    SELECT DISTINCT TEXT_ 
    FROM bronze.bpm_act_hi_varinst 
    WHERE NAME_ = 'moNumber' 
    AND TEXT_ LIKE 'Q%'
    LIMIT 10
""")
if result.result_rows:
    for row in result.result_rows:
        print(f"  {row[0]}")
else:
    print("  (無資料)")

# 查詢 R 開頭的 moNumber
print("\n=== R 開頭的 moNumber ===")
result = client.query("""
    SELECT DISTINCT TEXT_ 
    FROM bronze.bpm_act_hi_varinst 
    WHERE NAME_ = 'moNumber' 
    AND TEXT_ LIKE 'R%'
    LIMIT 10
""")
if result.result_rows:
    for row in result.result_rows:
        print(f"  {row[0]}")
else:
    print("  (無資料)")

# 統計各開頭的數量
print("\n=== moNumber 開頭字元統計 ===")
result = client.query("""
    SELECT 
        substring(TEXT_, 1, 1) AS first_char,
        count(*) AS cnt
    FROM bronze.bpm_act_hi_varinst 
    WHERE NAME_ = 'moNumber' 
    AND TEXT_ IS NOT NULL
    AND TEXT_ != ''
    GROUP BY first_char
    ORDER BY cnt DESC
    LIMIT 20
""")
for row in result.result_rows:
    print(f"  {row[0]}: {row[1]}")
