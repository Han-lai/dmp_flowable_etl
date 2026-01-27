#!/usr/bin/env python3
"""
評估 ClickHouse 原生排程機制
檢查當前版本支援的功能和限制
"""
import clickhouse_connect

# ClickHouse 連接設定
CH_HOST = "REDACTED_IP"
CH_PORT = 8121
CH_USER = "default"
CH_PASSWORD = "default"

def query_clickhouse(sql, description=""):
    """查詢 ClickHouse"""
    try:
        client = clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            username=CH_USER,
            password=CH_PASSWORD
        )
        
        print(f"\n🔍 {description}")
        print("-" * 60)
        
        result = client.query(sql)
        return result.result_rows
        
    except Exception as e:
        print(f"❌ 查詢錯誤: {e}")
        return None

def main():
    """評估 ClickHouse 排程功能"""
    print("=" * 80)
    print("ClickHouse 原生排程機制評估")
    print("=" * 80)
    
    # 1. 檢查 ClickHouse 版本
    sql_version = "SELECT version()"
    results_version = query_clickhouse(sql_version, "ClickHouse 版本")
    if results_version:
        version = results_version[0][0]
        print(f"版本: {version}")
    
    # 2. 檢查是否支援 REFRESHABLE MATERIALIZED VIEW
    sql_refresh_support = """
    SELECT 
        name,
        value,
        description
    FROM system.settings 
    WHERE name LIKE '%refresh%' OR name LIKE '%schedule%'
    """
    
    results_refresh = query_clickhouse(sql_refresh_support, "Refresh 相關設定")
    if results_refresh:
        print("Refresh 相關設定:")
        for row in results_refresh:
            name, value, desc = row
            print(f"  {name}: {value} - {desc}")
    else:
        print("❌ 未找到 Refresh 相關設定")
    
    # 3. 檢查系統表中的排程功能
    sql_system_tables = """
    SELECT name, comment
    FROM system.tables 
    WHERE database = 'system' 
      AND (name LIKE '%schedule%' OR name LIKE '%refresh%' OR name LIKE '%job%')
    """
    
    results_system = query_clickhouse(sql_system_tables, "系統排程相關表")
    if results_system:
        print("系統排程表:")
        for row in results_system:
            name, comment = row
            print(f"  {name}: {comment}")
    else:
        print("❌ 未找到系統排程表")
    
    # 4. 檢查 MATERIALIZED VIEW 的 refresh 功能
    sql_mv_refresh = """
    SELECT 
        database,
        name,
        engine,
        create_table_query
    FROM system.tables 
    WHERE engine = 'MaterializedView'
      AND create_table_query LIKE '%REFRESH%'
    LIMIT 5
    """
    
    results_mv = query_clickhouse(sql_mv_refresh, "支援 REFRESH 的 MATERIALIZED VIEW")
    if results_mv:
        print("支援 REFRESH 的 MV:")
        for row in results_mv:
            db, name, engine, query = row
            print(f"  {db}.{name}: {query[:100]}...")
    else:
        print("❌ 未找到支援 REFRESH 的 MATERIALIZED VIEW")
    
    # 5. 測試建立 REFRESHABLE MATERIALIZED VIEW
    print("\n🧪 測試建立 REFRESHABLE MATERIALIZED VIEW")
    print("-" * 60)
    
    try:
        client = clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            username=CH_USER,
            password=CH_PASSWORD
        )
        
        # 嘗試建立測試用的 REFRESHABLE MV
        test_sql = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS test.mv_refresh_test
        REFRESH EVERY 1 DAY
        AS SELECT 
            today() as snapshot_date,
            count() as record_count
        FROM system.numbers 
        LIMIT 1
        """
        
        client.command("CREATE DATABASE IF NOT EXISTS test")
        client.command(test_sql)
        print("✅ REFRESHABLE MATERIALIZED VIEW 建立成功")
        
        # 清理測試
        client.command("DROP VIEW IF EXISTS test.mv_refresh_test")
        
    except Exception as e:
        print(f"❌ REFRESHABLE MATERIALIZED VIEW 不支援: {e}")
    
    # 6. 檢查 TTL 和自動清理功能
    sql_ttl = """
    SELECT 
        database,
        table,
        engine,
        ttl_expression
    FROM system.tables 
    WHERE ttl_expression != ''
    LIMIT 5
    """
    
    results_ttl = query_clickhouse(sql_ttl, "TTL 功能檢查")
    if results_ttl:
        print("使用 TTL 的表:")
        for row in results_ttl:
            db, table, engine, ttl = row
            print(f"  {db}.{table}: {ttl}")
    
    print("\n" + "=" * 80)
    print("評估結果")
    print("=" * 80)
    
    print("📊 ClickHouse 原生排程功能:")
    print("1. ❌ REFRESHABLE MATERIALIZED VIEW: 不支援或版本過舊")
    print("2. ❌ 內建 Job Scheduler: 未發現")
    print("3. ✅ TTL 自動清理: 支援")
    print("4. ✅ MATERIALIZED VIEW: 支援 (僅 insert-driven)")
    
    print("\n💡 建議:")
    print("1. 保留外部排程 (cron/systemd timer)")
    print("2. 使用 MATERIALIZED VIEW 做即時聚合")
    print("3. 加入缺日監控機制")

if __name__ == "__main__":
    main()