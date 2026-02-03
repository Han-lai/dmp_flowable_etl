
import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

with open('sql/rebuild/04_silver_fact_tasks.sql', encoding='utf-8') as f:
    content = f.read()

# Split by semicolon and remove empty parts
statements = [s.strip() for s in content.split(';') if s.strip()]

print(f"Executing {len(statements)} statements from sql/rebuild/04_silver_fact_tasks.sql...")

for i, stmt in enumerate(statements):
    print(f"--- Statement {i+1} ---")
    try:
        res = client.command(stmt)
        if res is not None:
             print(res)
    except Exception as e:
        print(f"Error executing statement {i+1}: {e}")

print("\nDone.")
