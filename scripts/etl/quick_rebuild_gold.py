import clickhouse_connect
import re

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

client.command('DROP TABLE IF EXISTS gold.rmv_l5_task_completion')
client.command('DROP TABLE IF EXISTS gold.rmv_l5_task_completion_data')
client.command('DROP TABLE IF EXISTS gold.rmv_l5_task_completion_v2')
client.command('DROP TABLE IF EXISTS gold.rmv_l5_task_completion_v2_data')
client.command('DROP TABLE IF EXISTS gold.rmv_user_utilization')

def run_sql(filepath, replace_v1=False):
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Remove single-line comments before splitting
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    
    if replace_v1:
        sql = sql.replace("gold.rmv_l5_task_completion", "gold.rmv_l5_task_completion_v2")

    client.command("SET allow_experimental_refreshable_materialized_view = 1")
    
    statements = sql.split(';')
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        print(f"Executing: {stmt[:100].replace(chr(10), ' ')}...")
        result = client.command(stmt)
        print("Success:", str(result)[:100] if result else "None")

print("Rebuilding 06_gold_kpi_task_completion.sql as V2")
run_sql("sql/etl/06_gold_kpi_task_completion.sql", replace_v1=True)

print("Rebuilding 07_gold_kpi_user_utilization.sql")
run_sql("sql/etl/07_gold_kpi_user_utilization.sql", replace_v1=False)

print("Done rebuilding Gold layer.")
