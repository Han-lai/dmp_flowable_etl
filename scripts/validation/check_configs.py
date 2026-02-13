import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
conn = pyodbc.connect(conn_str)

def check_all_dmp_configs():
    print("=== All DMPFunctionConfig_0202 Records for E5 ===")
    df = pd.read_sql("""
        SELECT * FROM APP_SRV_COMMON.dbo.DMPFunctionConfig_0202
        WHERE Plant = 'WJ2' AND Factory = 'NBU' AND LineName = 'E5'
    """, conn)
    print(df.to_string(index=False))

    print("\n=== All DMPFunctionConfig (non-snapshot) Records for E5 ===")
    try:
        df2 = pd.read_sql("""
            SELECT * FROM APP_SRV_COMMON.dbo.DMPFunctionConfig
            WHERE Plant = 'WJ2' AND Factory = 'NBU' AND LineName = 'E5'
        """, conn)
        print(df2.to_string(index=False))
    except Exception as e:
        print(f"DMPFunctionConfig table not found or error: {e}")

    print("\n=== Checking for other similar tables ===")
    cursor = conn.cursor()
    cursor.execute("SELECT TABLE_NAME FROM APP_SRV_COMMON.INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'DMPFunction%'")
    for r in cursor.fetchall():
        print(f"Table: {r[0]}")

if __name__ == "__main__":
    check_all_dmp_configs()
    conn.close()
