import clickhouse_connect
import os

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', '10.146.206.76'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', '1qaz2wsx3edc'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def init_schema():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "sql", "etl", "schema", "06_gold_kpi_task_completion_v4.sql")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    print("Initialing V4 Schema in ClickHouse...")
    # Split by semicolon but ignore inside comments/strings if any (simple split here)
    for statement in schema_sql.split(';'):
        if statement.strip():
            print(f"Executing statement...")
            client.command(statement.strip())
    print("V4 Schema Initialized Successfully.")

if __name__ == "__main__":
    init_schema()
