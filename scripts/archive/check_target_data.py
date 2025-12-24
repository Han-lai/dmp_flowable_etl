"""檢查目標 MSSQL 資料"""
import pyodbc

TARGET_SERVER = "localhost"
TARGET_PORT = "1433"
TARGET_USER = "sa"
TARGET_PASSWORD = "YourStrong@Passw0rd"

def check_all():
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={TARGET_SERVER},{TARGET_PORT};"
        f"DATABASE=master;"
        f"UID={TARGET_USER};"
        f"PWD={TARGET_PASSWORD};"
    )
    
    print(f"連線到 {TARGET_SERVER}:{TARGET_PORT}/master...")
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        cursor = conn.cursor()
        print("連線成功!\n")
        
        # 列出所有資料庫
        cursor.execute("SELECT name FROM sys.databases")
        dbs = [row[0] for row in cursor.fetchall()]
        print(f"資料庫列表: {dbs}\n")
        
        # 檢查每個自訂資料庫的表格
        for db in ["APP_SRV_BPM", "APP_SRV_COMMON"]:
            print(f"=== {db} ===")
            try:
                cursor.execute(f"SELECT TABLE_NAME FROM [{db}].INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
                tables = [row[0] for row in cursor.fetchall()]
                
                if not tables:
                    print("  (無表格)")
                else:
                    for table in tables:
                        cursor.execute(f"SELECT COUNT(*) FROM [{db}].[dbo].[{table}]")
                        count = cursor.fetchone()[0]
                        print(f"  {table}: {count} 筆")
            except Exception as e:
                print(f"  錯誤: {e}")
            print()
        
        conn.close()
    except Exception as e:
        print(f"連線錯誤: {e}")

if __name__ == "__main__":
    check_all()
