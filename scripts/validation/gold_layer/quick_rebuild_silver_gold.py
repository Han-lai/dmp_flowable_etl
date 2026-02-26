import clickhouse_connect
import re

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

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
        print(f"Executing: {stmt[:100].replace(chr(10), ' ')}...")
        try:
            client.command(stmt)
        except Exception as e:
            if "UNKNOWN_TABLE" in str(e):
                continue
            print("Error:", e)

print("Rebuilding 03_silver_pivot...")
run_sql("sql/etl/03_silver_pivot_and_hierarchy.sql")

print("Rebuilding 04_silver_fact...")
run_sql("sql/etl/04_silver_fact_tasks.sql")

print("Rebuilding 06_gold_v2...")
client.command("DROP TABLE IF EXISTS gold.rmv_l5_task_completion_v2")
client.command("DROP TABLE IF EXISTS gold.rmv_l5_task_completion_v2_data")
run_sql("sql/etl/06_gold_kpi_task_completion.sql", replace_v1=True)

print("Done rebuilding Silver and Gold.")
