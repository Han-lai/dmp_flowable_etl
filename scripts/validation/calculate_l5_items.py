import clickhouse_connect
from datetime import datetime, timedelta

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def query_l5_items(client, table_name, is_gold=True):
    print(f"\n🔍 Querying table: {table_name}")
    print("-" * 80)
    
    # Cube Model Logic Mapping
    # Dimensions
    where_clause = """
        WHERE vx_type = 'V1'
          AND region = 'CNE'
          AND plant = 'WJ2'
          AND factory = 'NBU'
          AND line = 'E5'
    """
    
    date_col = "snapshot_date" if is_gold else "task_create_date"
    where_clause += f" AND {date_col} BETWEEN '2025-12-25' AND '2025-12-30'"
    
    # Measures
    if is_gold:
        measures = """
            snapshot_date,
            sum(total_task) as total_task,
            sum(todo_task) as todo_task,
            sum(doing_task) as doing_task,
            sum(done_task) as done_task
        """
        group_by = "GROUP BY snapshot_date"
        order_by = "ORDER BY snapshot_date"
    else:
        # Silver Logic (Aggregating from granular data)
        measures = """
            task_create_date as snapshot_date,
            count(*) as total_task,
            countIf(task_status = 'TODO') as todo_task,
            countIf(task_status = 'DOING') as doing_task,
            countIf(task_status = 'DONE') as done_task
        """
        where_clause += " AND is_excluded = 0"
        group_by = "GROUP BY task_create_date"
        order_by = "ORDER BY task_create_date"

    sql = f"""
        SELECT 
            {measures}
        FROM {table_name}
        {where_clause}
        {group_by}
        {order_by}
    """
    
    try:
        result = client.query(sql)
        
        if not result.result_rows:
            print("⚠️ No data found with these criteria.")
            return False

        print(f"{'Date':<12} | {'Total':<8} | {'Todo':<8} | {'Doing':<8} | {'Done':<8} | {'Todo%':<8} | {'Doing%':<8} | {'Done%':<8}")
        print("-" * 80)
        
        for row in result.result_rows:
            date_val, total, todo, doing, done = row
            # Calculate Rates (Cube Model Logic)
            todo_rate = (todo / total * 100) if total > 0 else 0
            doing_rate = (doing / total * 100) if total > 0 else 0
            done_rate = (done / total * 100) if total > 0 else 0
            
            print(f"{date_val:<12} | {total:<8} | {todo:<8} | {doing:<8} | {done:<8} | {todo_rate:<7.1f}% | {doing_rate:<7.1f}% | {done_rate:<7.1f}%")
            
        return True

    except Exception as e:
        print(f"❌ Query failed: {e}")
        return False

def main():
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        # 1. Try Gold Layer (Primary Source for Cube)
        print("Attempting to query Gold Layer (Cube Source)...")
        gold_success = query_l5_items(client, "gold.l5_dashboard_summary", is_gold=True)
        
        if not gold_success:
            print("\n⚠️ Gold layer has no data. Checking Silver Layer (Source of Gold)...")
            print("Note: If Silver has data but Gold does not, run 'scripts/execute_gold_dimension_update.py' to refresh Gold.")
            query_l5_items(client, "silver.mv_fact_task_vx_attribution_mdm", is_gold=False)

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    main()
