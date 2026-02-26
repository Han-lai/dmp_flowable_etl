import clickhouse_connect
import re

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

client.command("DROP TABLE IF EXISTS silver.mv_fact_task_vx")
client.command("DROP TABLE IF EXISTS gold.rmv_l5_task_completion_v2")
client.command("DROP TABLE IF EXISTS gold.rmv_l5_task_completion_v2_data")

def run_sql(filepath, replace_v1=False):
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    
    if replace_v1:
        sql = sql.replace("gold.rmv_l5_task_completion", "gold.rmv_l5_task_completion_v2")

    client.command("SET allow_experimental_refreshable_materialized_view = 1")
    
    statements = sql.split(';')
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            client.command(stmt)
        except Exception as e:
            if "UNKNOWN_TABLE" in str(e):
                continue
            print("Error:", e)

print("Rebuilding 04_silver_fact...")
run_sql("sql/etl/04_silver_fact_tasks.sql")

print("Rebuilding 06_gold_v2...")
run_sql("sql/etl/06_gold_kpi_task_completion.sql", replace_v1=True)

print("Done rebuilding Silver Fact and Gold.")
