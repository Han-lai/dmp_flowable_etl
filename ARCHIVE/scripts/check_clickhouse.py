"""檢查 ClickHouse 狀態和表格"""
import requests

CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = "8123"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASSWORD = "default"

def query(sql: str):
    """執行 ClickHouse 查詢"""
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}/"
    params = {
        "user": CLICKHOUSE_USER,
        "password": CLICKHOUSE_PASSWORD,
        "query": sql
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.text.strip()
        else:
            return f"Error: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"Connection Error: {e}"

def main():
    print("=" * 60)
    print("ClickHouse 狀態檢查")
    print("=" * 60)
    
    # 1. 測試連線
    print("\n1. 測試連線...")
    result = query("SELECT 1")
    if result == "1":
        print("   ✅ ClickHouse 連線成功!")
    else:
        print(f"   ❌ 連線失敗: {result}")
        return
    
    # 2. 版本資訊
    print("\n2. 版本資訊...")
    version = query("SELECT version()")
    print(f"   版本: {version}")
    
    # 3. 列出所有資料庫
    print("\n3. 資料庫列表...")
    dbs = query("SELECT name FROM system.databases ORDER BY name")
    for db in dbs.split('\n'):
        if db:
            print(f"   - {db}")
    
    # 4. 檢查 bronze 資料庫
    print("\n4. Bronze 資料庫表格...")
    tables = query("SELECT name FROM system.tables WHERE database = 'bronze' ORDER BY name")
    if tables:
        for table in tables.split('\n'):
            if table:
                count = query(f"SELECT count() FROM bronze.{table}")
                print(f"   - {table}: {count} 筆")
    else:
        print("   (bronze 資料庫不存在或無表格)")
    
    # 5. 測試 JDBC Bridge
    print("\n5. 測試 JDBC Bridge...")
    jdbc_test = query("SELECT * FROM jdbc('mssql_bpm', 'SELECT TOP 1 1 as test')")
    if "Error" in jdbc_test or "Exception" in jdbc_test:
        print(f"   ❌ JDBC Bridge 失敗: {jdbc_test[:200]}")
    else:
        print(f"   ✅ JDBC Bridge 正常!")
        
        # 測試 MSSQL 連線
        print("\n6. 測試 MSSQL 資料...")
        mssql_test = query("SELECT * FROM jdbc('mssql_bpm', 'SELECT TOP 1 ID_ FROM ACT_HI_PROCINST')")
        if "Error" in mssql_test or "Exception" in mssql_test:
            print(f"   ❌ MSSQL 查詢失敗: {mssql_test[:200]}")
        else:
            print(f"   ✅ MSSQL 查詢成功! 範例 ID: {mssql_test}")

if __name__ == "__main__":
    main()
