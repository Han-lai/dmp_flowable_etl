import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01 S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

# Correcting the server name (removed space)
server = 'WJOAUATDB01S.delta.corp,65000'

conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
conn = pyodbc.connect(conn_str)

def check_fts_nov():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    dates = pd.date_range(start='2025-11-24', end='2025-11-30').strftime('%Y-%m-%d').tolist()
    
    print(f"=== FlowableTaskStats_0202 Counts for Nov 24-30 ===")
    
    # User expects: 14, 10, 9, 8, 9, 9, 1? (Or something close)
    # The 8th value '1' is Sunday 30th.
    
    query = f"""
    SELECT TaskEndDate, COUNT(DISTINCT TaskAssignee) as UniqueUsers
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats_0202
    WHERE Plant = '{plant}' AND Factory = '{factory}' AND Line = '{line}'
      AND TaskEndDate BETWEEN '2025-11-24' AND '2025-11-30'
    GROUP BY TaskEndDate
    ORDER BY TaskEndDate
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))

if __name__ == "__main__":
    check_fts_nov()
    conn.close()
