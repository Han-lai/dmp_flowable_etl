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

print("=== Looking for Calendar/Holiday tables ===")
query = """
SELECT TABLE_SCHEMA, TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_NAME LIKE '%CALENDAR%' OR TABLE_NAME LIKE '%HOLIDAY%'
"""
df = pd.read_sql(query, conn)
print(df.to_string(index=False))

# Also search in APP_SRV_COMMON
query_common = """
SELECT TABLE_SCHEMA, TABLE_NAME 
FROM APP_SRV_COMMON.INFORMATION_SCHEMA.TABLES 
WHERE TABLE_NAME LIKE '%CALENDAR%' OR TABLE_NAME LIKE '%HOLIDAY%'
"""
df_common = pd.read_sql(query_common, conn)
print("\n=== Tables in APP_SRV_COMMON ===")
print(df_common.to_string(index=False))

conn.close()
