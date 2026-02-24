import clickhouse_connect
import sys

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

PLANT = 'DG3'
FACTORY = 'SMT'
LINE = 'ST02'

def execute_backfill():
    print(f"Executing Gold Backfill for {PLANT}/{FACTORY}/{LINE}...")
    
    try:
        # 1. Find Inner Table (Newest one, corresponding to V2)
        print("Finding inner table...")
        r_tables = client.query("SELECT name FROM system.tables WHERE database='gold' AND name LIKE '.inner_id.%' ORDER BY metadata_modification_time DESC LIMIT 1")
        if not r_tables.result_rows:
            print("❌ No inner tables found!")
            return
            
        target_table = r_tables.result_rows[0][0]
        print(f"Found target inner table: {target_table}")
        
        # Check columns of target
        r_desc = client.query(f"DESCRIBE gold.`{target_table}`")
        target_cols = [row[0] for row in r_desc.result_rows]
        print(f"Target Columns: {target_cols}")
        
        # Map output columns based on target inner table
        if 'plant_code' in target_cols:
            p_col = 'plant_code'
            f_col = 'factory_code'
            l_col = 'line_name'
        else:
            p_col = 'plant'
            f_col = 'factory'
            l_col = 'line' # Default from DDL
            
        print(f"Using aliases: {p_col}, {f_col}, {l_col}")
        
        # 2. Construct Backfill Query
        
        backfill_sql = f"""
        INSERT INTO gold.`{target_table}` ({", ".join(target_cols)})
        SELECT
            snapshot_date,
            vx_type,
            {'region_code' if 'region_code' in target_cols else 'region'} AS region,
            {p_col} AS plant,
            {f_col} AS factory,
            {l_col} AS line,
            total_task,
            todo_count,
            doing_count,
            done_count,
            completion_rate,
            execution_rate,
            acc_todo_doing,
            now64(3) AS _refresh_time
        FROM
        (
            WITH
                daily_base AS
                (
                    SELECT
                        snapshot_date,
                        vx_type,
                        region,
                        plant,
                        factory,
                        line,
                        count() AS total_task,
                        countIf((snapshot_date < toDate(task_claim_date)) OR ((snapshot_date < toDate(task_end_date)) AND (task_claim_date IS NULL))) AS todo_count,
                        countIf((snapshot_date >= toDate(task_claim_date)) AND ((snapshot_date < toDate(task_end_date)) OR (task_end_date IS NULL))) AS doing_count,
                        countIf((snapshot_date >= toDate(task_end_date)) AND ((task_end_date IS NULL) = 0)) AS done_count
                    FROM silver.mv_fact_task_vx
                    FINAL
                    ARRAY JOIN arrayDistinct(arrayFilter(d -> (d IS NOT NULL), [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
                    WHERE is_excluded = 0
                      AND plant = '{PLANT}'
                      AND factory = '{FACTORY}'
                      AND line = '{LINE}'
                    GROUP BY
                        snapshot_date,
                        vx_type,
                        region,
                        plant,
                        factory,
                        line
                ),
                acc_stats AS
                (
                    SELECT
                        dates.snapshot_date,
                        tasks.vx_type,
                        tasks.region,
                        tasks.plant,
                        tasks.factory,
                        tasks.line,
                        uniqExact(tasks.task_id) AS acc_todo_doing
                    FROM
                    (
                        SELECT DISTINCT snapshot_date
                        FROM silver.mv_fact_task_vx
                        ARRAY JOIN arrayDistinct(arrayFilter(d -> (d IS NOT NULL), [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
                        WHERE is_excluded = 0
                          AND plant = '{PLANT}'
                          AND factory = '{FACTORY}'
                          AND line = '{LINE}'
                    ) AS dates
                    CROSS JOIN silver.mv_fact_task_vx AS tasks
                    WHERE (tasks.is_excluded = 0)
                      AND (tasks.plant = '{PLANT}' AND tasks.factory = '{FACTORY}' AND tasks.line = '{LINE}')
                      AND (tasks.task_start_date <= dates.snapshot_date) 
                      AND ((tasks.task_end_date IS NULL) OR (tasks.task_end_date > dates.snapshot_date)) 
                      AND ((tasks.task_start_date >= subtractDays(dates.snapshot_date, 6)) OR ((tasks.task_claim_date IS NOT NULL) AND (tasks.task_claim_date >= subtractDays(dates.snapshot_date, 6))))
                    GROUP BY
                        dates.snapshot_date,
                        tasks.vx_type,
                        tasks.region,
                        tasks.plant,
                        tasks.factory,
                        tasks.line
                )
            SELECT
                coalesce(base.snapshot_date, acc.snapshot_date) AS snapshot_date,
                coalesce(base.vx_type, acc.vx_type) AS vx_type,
                coalesce(base.region, acc.region) AS region,
                coalesce(base.plant, acc.plant) AS plant,
                coalesce(base.factory, acc.factory) AS factory,
                coalesce(base.line, acc.line) AS line,
                coalesce(base.total_task, 0) AS total_task,
                coalesce(base.todo_count, 0) AS todo_count,
                coalesce(base.doing_count, 0) AS doing_count,
                coalesce(base.done_count, 0) AS done_count,
                round((coalesce(base.done_count, 0) * 100.) / nullIf(coalesce(base.total_task, 0), 0), 2) AS completion_rate,
                round(((coalesce(base.doing_count, 0) + coalesce(base.done_count, 0)) * 100.) / nullIf(coalesce(base.total_task, 0), 0), 2) AS execution_rate,
                coalesce(acc.acc_todo_doing, 0) AS acc_todo_doing,
                now64(3) AS _refresh_time
            FROM daily_base AS base
            FULL OUTER JOIN acc_stats AS acc USING (snapshot_date, vx_type, region, plant, factory, line)
        )
        """
        
        # Execute
        print("Executing SQL (Inner Table)...")
        client.query(backfill_sql)
        print("✅ Backfill SQL executed successfully.")
        
        # Verify
        print("Verifying Backfill...")
        verify_q = f"""
        SELECT count() 
        FROM gold.`{target_table}`
        WHERE {p_col}='{PLANT}' 
          AND {f_col}='{FACTORY}' 
          AND {l_col}='{LINE}'
        """
        r_ver = client.query(verify_q)
        cnt = r_ver.result_rows[0][0]
        print(f"Gold rows for {PLANT}/{FACTORY}/{LINE}: {cnt}")
        
    except Exception as e:
        print(f"Error during backfill: {e}")

if __name__ == "__main__":
    execute_backfill()
