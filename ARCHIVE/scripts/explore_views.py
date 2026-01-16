import clickhouse_connect

# 參考環境
client = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

# 直接查詢 silver_enriched_taskinst 的完整定義
print("=== silver_enriched_taskinst 完整定義 ===")
result = client.query("SHOW CREATE VIEW flowable_analytics.silver_enriched_taskinst")
print(result.result_rows[0][0])
