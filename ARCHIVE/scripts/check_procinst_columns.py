"""查詢 ACT_HI_PROCINST 表結構和範例資料"""
import clickhouse_connect

client = clickhouse_connect.get_client(
    host="10.136.218.207",
    port=8121,
    username="default",
    password="default"
)

# 查詢欄位
print("=== ACT_HI_PROCINST 欄位 ===")
result = client.query("SELECT * FROM bronze.bpm_act_hi_procinst LIMIT 1")
print("Columns:", result.column_names)

# 查詢 NAME_ 欄位範例
print("\n=== NAME_ 欄位範例 ===")
result = client.query("""
    SELECT DISTINCT NAME_ 
    FROM bronze.bpm_act_hi_procinst 
    WHERE NAME_ IS NOT NULL 
    LIMIT 20
""")
for row in result.result_rows:
    print(f"  {row[0]}")

# 查詢 BUSINESS_KEY_ 欄位範例
print("\n=== BUSINESS_KEY_ 欄位範例 ===")
result = client.query("""
    SELECT DISTINCT BUSINESS_KEY_ 
    FROM bronze.bpm_act_hi_procinst 
    WHERE BUSINESS_KEY_ IS NOT NULL 
    LIMIT 20
""")
for row in result.result_rows:
    print(f"  {row[0]}")

# 查詢工單編號 196/200/210/212/213 開頭的範例
print("\n=== 工單編號 196/200/210/212/213 開頭的 NAME_ 範例 ===")
result = client.query("""
    SELECT DISTINCT NAME_ 
    FROM bronze.bpm_act_hi_procinst 
    WHERE NAME_ LIKE '%196%' 
       OR NAME_ LIKE '%200%' 
       OR NAME_ LIKE '%210%'
       OR NAME_ LIKE '%212%'
       OR NAME_ LIKE '%213%'
    LIMIT 10
""")
for row in result.result_rows:
    print(f"  {row[0]}")

# 查詢 Q 工單範例
print("\n=== Q 工單範例 (NAME_ LIKE 'Q%') ===")
result = client.query("""
    SELECT DISTINCT NAME_ 
    FROM bronze.bpm_act_hi_procinst 
    WHERE NAME_ LIKE 'Q%'
    LIMIT 10
""")
for row in result.result_rows:
    print(f"  {row[0]}")

# 查詢 R 工單範例
print("\n=== R 工單範例 (NAME_ LIKE 'R%') ===")
result = client.query("""
    SELECT DISTINCT NAME_ 
    FROM bronze.bpm_act_hi_procinst 
    WHERE NAME_ LIKE 'R%'
    LIMIT 10
""")
for row in result.result_rows:
    print(f"  {row[0]}")

# 查詢 NPE 範例
print("\n=== NPE 範例 (BUSINESS_KEY_ LIKE '%NPE%') ===")
result = client.query("""
    SELECT DISTINCT BUSINESS_KEY_ 
    FROM bronze.bpm_act_hi_procinst 
    WHERE BUSINESS_KEY_ LIKE '%NPE%'
    LIMIT 10
""")
for row in result.result_rows:
    print(f"  {row[0]}")
