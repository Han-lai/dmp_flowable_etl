import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

def create_v2():
    print("Creating Gold View V2...")
    try:
        with open('gold_ddl.sql', 'r', encoding='utf-8') as f:
            ddl = f.read()
            
        # Modify DDL to use V2 name
        ddl_v2 = ddl.replace("gold.rmv_l5_task_completion", "gold.rmv_l5_task_completion_v2")
        
        # Enable experimental features
        client.query("SET allow_experimental_refreshable_materialized_view=1")
        client.query(ddl_v2)
        print("Gold View V2 created successfully.")
        
    except Exception as e:
        print(f"Error creating V2: {e}")

if __name__ == "__main__":
    create_v2()
