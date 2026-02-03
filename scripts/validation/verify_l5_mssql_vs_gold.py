import clickhouse_connect
import sys
from datetime import datetime

# MSSQL Validation Logic (Simulated via JDBC Bridge Query)
# Source: APP_SRV_COMMON.dbo.FlowableTaskStats_0202

def get_client():
    return clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

def check_mssql_source(client):
    print("Fetching Truth from MSSQL (APP_SRV_COMMON.dbo.FlowableTaskStats_0202)...")
    
    # 2025-12-25 Scope
    # Note: FlowableTaskStats logic: StartDate or EndDate falls in range
    # But usually dashboard uses CreateTime or EndTime.
    # Let's assume the user wants standard dashboard day logic.
    query = """
    SELECT 
        VxType,
        COUNT(*) as Total,
        SUM(CASE WHEN TaskStatus = 'DONE' THEN 1 ELSE 0 END) as Done,
        SUM(CASE WHEN TaskStatus = 'TODO' THEN 1 ELSE 0 END) as Todo,
        SUM(CASE WHEN TaskStatus = 'DOING' THEN 1 ELSE 0 END) as Doing
    FROM jdbc('mssql_master', '
        SELECT *
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats_0202
        WHERE Plant = ''WJ2'' 
          AND Factory = ''NBU'' 
          AND LineName = ''E5''
          AND (
            CAST(TaskCreateTime AS DATE) = ''2025-12-25''
            OR CAST(TaskEndTime AS DATE) = ''2025-12-25''
          )
    ')
    GROUP BY VxType
    ORDER BY VxType
    """
    return client.query(query).result_rows

def check_gold_target(client):
    print("Fetching Target from ClickHouse Gold (rmv_l5_task_completion)...")
    
    # Gold layer is aggregated by hour, so we sum up for the day
    query = """
    SELECT 
        vx_type,
        sum(total_tasks) as Total,
        sum(done_tasks) as Done,
        sum(todo_tasks) as Todo,
        sum(doing_tasks) as Doing
    FROM gold.rmv_l5_task_completion
    WHERE plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
      AND toDate(snapshot_date) = '2025-12-25'
    GROUP BY vx_type
    ORDER BY vx_type
    """
    return client.query(query).result_rows

def main():
    client = get_client()
    
    try:
        mssql_rows = check_mssql_source(client)
        print("\n=== MSSQL Source (Truth) ===")
        print(f"{'VxType':<10} {'Total':<10} {'Done':<10} {'Todo':<10} {'Doing':<10}")
        mssql_map = {}
        for row in mssql_rows:
            vx, total, done, todo, doing = row
            print(f"{vx:<10} {total:<10} {done:<10} {todo:<10} {doing:<10}")
            mssql_map[vx] = {'Total': total, 'Done': done}

        gold_rows = check_gold_target(client)
        print("\n=== ClickHouse Gold (Target) ===")
        print(f"{'VxType':<10} {'Total':<10} {'Done':<10} {'Todo':<10} {'Doing':<10}")
        gold_map = {}
        for row in gold_rows:
            vx, total, done, todo, doing = row
            print(f"{vx:<10} {total:<10} {done:<10} {todo:<10} {doing:<10}")
            gold_map[vx] = {'Total': total, 'Done': done}
            
        # Comparison
        print("\n=== Comparison Result ===")
        all_passed = True
        all_vxs = set(mssql_map.keys()) | set(gold_map.keys())
        
        for vx in sorted(all_vxs):
            m = mssql_map.get(vx, {'Total': 0, 'Done': 0})
            g = gold_map.get(vx, {'Total': 0, 'Done': 0})
            
            diff_total = g['Total'] - m['Total']
            diff_done = g['Done'] - m['Done']
            
            status = "✅ MATCH"
            if diff_total != 0 or diff_done != 0:
                status = "❌ MISMATCH"
                all_passed = False
                
            print(f"[{status}] {vx:<5} | Total: {m['Total']} vs {g['Total']} (Diff: {diff_total}) | Done: {m['Done']} vs {g['Done']} (Diff: {diff_done})")
            
        if all_passed:
            print("\n🎉 VALIDATION SUCCESS: Data matches perfectly.")
        else:
            print("\n⚠️ VALIDATION FAILED: Differences detected.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
