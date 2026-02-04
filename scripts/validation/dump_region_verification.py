import clickhouse_connect

def dump_data():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    query = """
    SELECT 
        task_id,
        proc_inst_id,
        task_start_date,
        region,
        region_source,
        plant,
        factory,
        line,
        vx_type,
        mo_number
    FROM silver.mv_fact_task_vx FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_start_date BETWEEN '2025-12-22' AND '2025-12-28'
    LIMIT 10
    """
    result = client.query(query)
    with open('region_verification_details.csv', 'w', encoding='utf-8') as f:
        f.write(','.join(result.column_names) + '\n')
        for row in result.result_set:
            f.write(','.join([str(v) for v in row]) + '\n')

if __name__ == "__main__":
    dump_data()
