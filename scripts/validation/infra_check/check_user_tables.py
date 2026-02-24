import clickhouse_connect
import sys

# Config
host = 'REDACTED_IP'
port = 8121
username = 'default'
password = 'default'

def run_query():
    try:
        print(f"Connecting to ClickHouse {host}...")
        client = clickhouse_connect.get_client(host=host, port=port, username=username, password=password)
        
        tables = [
            'default.common_emp_user_group_mapping',
            'default.common_user_group',
            'default.common_emp_node_role_mapping',
            'default.common_emp_org_info_mapping',
            'default.common_process_role_user_mapping'
        ]
        
        for table in tables:
            try:
                count = client.command(f"SELECT count(*) FROM {table}")
                print(f"{table}: {count}")
            except Exception as e:
                print(f"{table}: Iteration Error - {e}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_query()
