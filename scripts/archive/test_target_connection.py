"""測試目標 MSSQL 連線"""
import pyodbc

TARGET_SERVER = "localhost"
TARGET_PORT = "1433"
TARGET_USER = "sa"
TARGET_PASSWORD = "YourStrong@Passw0rd"

# 先連到 master 建立資料庫
conn_str = (
    f"DRIVER={{SQL Server}};"
    f"SERVER={TARGET_SERVER},{TARGET_PORT};"
    f"DATABASE=master;"
    f"UID={TARGET_USER};"
    f"PWD={TARGET_PASSWORD};"
    f"Connection Timeout=10;"
)

print(f"連線到 {TARGET_SERVER}:{TARGET_PORT}...")
try:
    conn = pyodbc.connect(conn_str, timeout=10)
    print("✅ 連線成功!")
    
    cursor = conn.cursor()
    
    # 建立資料庫
    for db_name in ["APP_SRV_BPM", "APP_SRV_COMMON"]:
        cursor.execute(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{db_name}') CREATE DATABASE [{db_name}]")
        print(f"✅ 資料庫 {db_name} 已確認/建立")
    
    conn.commit()
    conn.close()
    print("✅ 完成!")
    
except Exception as e:
    print(f"❌ 連線失敗: {e}")
