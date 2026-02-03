
import pyodbc

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'

def check_table_in_db(db_name):
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={db_name};UID={username};PWD={password}'
    try:
        conn = pyodbc.connect(conn_str, timeout=3)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sys.tables WHERE name LIKE '%FlowableTaskStats%'")
        tables = [row.name for row in cursor.fetchall()]
        conn.close()
        return tables
    except:
        return []

dbs = ['APP_SRV_BPM', 'APP_SRV_COMMON', 'APP_SRV_V1', 'APP_SRV_V2', 'APP_SRV_V3', 'SMS', 'EVM', 'AYA', 'MFG']

print("Searching for FlowableTaskStats tables...")
for db in dbs:
    found = check_table_in_db(db)
    if found:
        print(f"Database {db}: {found}")
