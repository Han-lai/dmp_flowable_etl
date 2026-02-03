
import clickhouse_connect
import sys

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse...")
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # 1. Identify New Table
    print("\n--- Step 0: Identify New Table (FlowableTaskStats_0202) ---")
    new_table = None
    try:
        res = client.query("SHOW TABLES FROM bronze LIKE '%0202%'")
        if res.result_rows:
            tables = [r[0] for r in res.result_rows]
            print(f"Found candidate tables: {tables}")
            # heuristic: pick the one looking like flowable_task_stats
            for t in tables:
                if 'flowable' in t.lower() and 'stats' in t.lower():
                    new_table = f"bronze.{t}"
                    break
            if not new_table and tables:
                new_table = f"bronze.{tables[0]}" # Fallback
        else:
            print("No table found with '0202' in name in bronze database.")
    except Exception as e:
        print(f"Error checking tables: {e}")

    old_table = "bronze.common_flowable_task_stats"
    print(f"Old Source: {old_table}")
    print(f"New Source: {new_table if new_table else 'NOT FOUND'}")

    if not new_table:
        print("Cannot proceed with comparison without new table.")
        return

    # 2. Define Query Function
    def run_verification(table_name, label):
        print(f"\n--- Running Verification on {label} ({table_name}) ---")
        query = f"""
        SELECT 
            count() AS total_task,
            countIf(upper(TaskStatus) = 'TODO') AS todo,
            countIf(upper(TaskStatus) = 'DOING') AS doing,
            countIf(upper(TaskStatus) = 'DONE') AS done,
            round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate,
            round(countIf(upper(TaskStatus) IN ('DOING', 'DONE')) * 100.0 / count(), 2) AS execution_rate
        FROM {table_name} FINAL
        WHERE 
            Plant = 'WJ2' AND Factory = 'NBU' AND Line = 'E5'
            AND (toDate(TaskCreateTime) = '2025-12-25'
                 OR toDate(TaskClaimTime) = '2025-12-25'
                 OR toDate(TaskEndTime) = '2025-12-25')
            AND (TaskBypass = 'N' OR TaskBypass IS NULL)
            AND TaskDefinitionKey NOT LIKE 'E%'
            AND TaskDefinitionKey NOT LIKE 'C%'
            AND (MoNumber NOT LIKE 'Q%' OR MoNumber IS NULL)
            AND (MoNumber NOT LIKE 'R%' OR MoNumber IS NULL)
        """
        try:
            res = client.query(query)
            row = res.result_rows[0]
            print(f"[{label}] Results:")
            print(f"  Total: {row[0]}")
            print(f"  Todo: {row[1]}")
            print(f"  Doing: {row[2]}")
            print(f"  Done: {row[3]}")
            print(f"  Rate: {row[4]}%")
            print(f"  Exec: {row[5]}%")
            return row
        except Exception as e:
            print(f"Error querying {label}: {e}")
            return None

    # 3. Run Comparisons
    old_res = run_verification(old_table, "OLD")
    new_res = run_verification(new_table, "NEW")

    # 4. Output Summary Table
    if old_res and new_res:
        print("\n=== Comparison Report ===")
        print(f"{'Metric':<15} | {'Old Table':<10} | {'New Table':<10} | {'Diff':<10}")
        print("-" * 55)
        metrics = ['total_count', 'todo_count', 'doing_count', 'done_count', 'completion_rate', 'execution_rate']
        for i, m in enumerate(metrics):
            old_val = old_res[i]
            new_val = new_res[i]
            diff = round(new_val - old_val, 2)
            print(f"{m:<15} | {str(old_val):<10} | {str(new_val):<10} | {str(diff):<10}")

if __name__ == "__main__":
    main()
