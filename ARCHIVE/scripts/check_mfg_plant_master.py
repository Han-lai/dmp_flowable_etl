"""查詢 MDM_MFG_PLANT_MASTER 表結構"""
import clickhouse_connect

client = clickhouse_connect.get_client(
    host="REDACTED_IP",
    port=8121,
    username="default",
    password="default"
)

sql = """
SELECT * FROM jdbc('mssql_master', 'SELECT TOP 1 * FROM APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER')
"""

result = client.query(sql)
print("Columns:", result.column_names)
print("Sample:", result.result_rows[0] if result.result_rows else "No data")

# 查詢筆數
count_sql = """
SELECT count(*) FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER')
"""
count = client.command(count_sql)
print(f"Total rows: {count}")
