import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def check_dimensions(client):
    print("🔍 Analyzing Gold Layer Dimensions (gold.l5_dashboard_summary)")
    print("-" * 80)

    # 1. Total Rows
    total = client.query("SELECT count(*) FROM gold.l5_dashboard_summary").result_rows[0][0]
    print(f"Total Rows: {total}")

    # 2. Plant Missing Analysis
    sql_missing = """
        SELECT 
            plant, 
            plant_source,
            count(*) as count,
            round(count(*) * 100.0 / (SELECT count(*) FROM gold.l5_dashboard_summary), 2) as pct
        FROM gold.l5_dashboard_summary 
        GROUP BY plant, plant_source 
        ORDER BY count DESC 
        LIMIT 20
    """
    print("\n📊 Plant Distribution (Top 20):")
    print(f"{'Plant':<20} | {'Source':<10} | {'Count':<8} | {'%':<6}")
    print("-" * 60)
    for row in client.query(sql_missing).result_rows:
        print(f"{row[0]:<20} | {row[1]:<10} | {row[2]:<8} | {row[3]}%")

    # 3. Dimension Cardinality (Explosion Check)
    sql_cardinality = """
        SELECT count(distinct (region, plant, factory, line)) 
        FROM gold.l5_dashboard_summary
    """
    cardinality = client.query(sql_cardinality).result_rows[0][0]
    print(f"\n💥 Distinct Dimension Combinations: {cardinality}")
    
    if cardinality > 1000:
        print("⚠️ HIGH CARDINALITY DETECTED! Possible dimension explosion.")
    else:
        print("✅ Cardinality seems reasonable.")

    # 4. Drill down into 'MISSING' source if significant
    sql_missing_detail = """
        SELECT 
            vx_type,
            count(*) as count
        FROM gold.l5_dashboard_summary 
        WHERE plant_source = 'MISSING' OR plant = ''
        GROUP BY vx_type
        ORDER BY count DESC
    """
    print("\n🔍 Breakdown of MISSING/Empty Plant by Vx Type:")
    print(f"{'Vx Type':<10} | {'Count':<8}")
    print("-" * 30)
    res = client.query(sql_missing_detail).result_rows
    if not res:
        print("(No missing plant rows found)")
    for row in res:
        print(f"{row[0]:<10} | {row[1]:<8}")

def main():
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        check_dimensions(client)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
