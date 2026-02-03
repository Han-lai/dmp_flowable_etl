
import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

# The user's query logic
# We need to find the correct database/schema in MSSQL for FlowableTaskStats_0202
# Based on project context, it's likely APP_SRV_COMMON or similar.
# Let's try to query it via ClickHouse JDBC bridge.

mssql_query = """
SELECT count(*) 
FROM APP_SRV_COMMON.dbo.FlowableTaskStats_0202 
WHERE (
    CAST(TaskCreateDate AS DATE) = ''2025-12-25''
    OR CAST(TaskEndDate AS DATE) = ''2025-12-25''
    OR CAST(TaskClaimDate AS DATE) = ''2025-12-25''
)
AND TaskBypass = ''N'' 
AND TaskStatus IN (''DONE'')
AND (
    MoNumber NOT LIKE ''E%'' 
    AND MoNumber NOT LIKE ''C%'' 
    AND MoNumber NOT LIKE ''Q%'' 
    AND MoNumber NOT LIKE ''R%''
)
"""

print("--- Querying MSSQL FlowableTaskStats_0202 ---")
try:
    # Use JDBC Bridge
    ch_query = f"SELECT * FROM jdbc('mssql_master', '{mssql_query}')"
    res = client.command(ch_query)
    print(f"Count from FlowableTaskStats_0202: {res}")
except Exception as e:
    print(f"Error querying FlowableTaskStats_0202: {e}")
    print("Trying alternative table name 'FlowableTaskStats' in flowable_analytics (if exists in CH or MSSQL)...")
    
    # Try another common name seen in project
    try:
        mssql_query_alt = """
        SELECT count(*) 
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats 
        WHERE (
            CAST(TaskCreateDate AS DATE) = ''2025-12-25''
            OR CAST(TaskEndDate AS DATE) = ''2025-12-25''
            OR CAST(TaskClaimDate AS DATE) = ''2025-12-25''
        )
        AND TaskBypass = ''N'' 
        AND TaskStatus IN (''DONE'')
        """
        ch_query_alt = f"SELECT * FROM jdbc('mssql_master', '{mssql_query_alt}')"
        res_alt = client.command(ch_query_alt)
        print(f"Count from FlowableTaskStats (Standard): {res_alt}")
    except Exception as e2:
        print(f"Error querying FlowableTaskStats: {e2}")

# Also compare with current Gold count for reference
gold_filters = "plant='WJ2' AND factory='NBU' AND line='E5' AND toDate(snapshot_date)='2025-12-25'"
gold_res = client.command(f"SELECT sum(total_task) FROM gold.rmv_l5_task_completion WHERE {gold_filters}")
print(f"Current ClickHouse Gold Count: {gold_res}")
