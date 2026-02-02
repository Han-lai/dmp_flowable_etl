import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\n比較變數表 (VARINST) 資料總量:")
    
    table_mssql = "APP_SRV_BPM.dbo.ACT_HI_VARINST_0108"
    table_ch = "bronze.bpm_act_hi_varinst"
    
    # 1. MSSQL Count
    try:
        count_sql = f"SELECT count(*) FROM {table_mssql}"
        mssql_count = client.query(f"SELECT * FROM jdbc('mssql_master', '{count_sql}')").result_rows[0][0]
        print(f"MSSQL ({table_mssql}): {mssql_count:,}")
    except Exception as e:
        print(f"MSSQL Error: {e}")

    # 2. ClickHouse Count
    try:
        ch_count = client.command(f"SELECT count() FROM {table_ch}")
        print(f"ClickHouse ({table_ch}):   {ch_count:,}")
    except Exception as e:
        print(f"CH Error: {e}")
        
    print("\n")
    if abs(mssql_count - ch_count) < 1000:
        print("✅ 變數表資料量大致一致")
    else:
        print("❌ 變數表資料量有顯著差異")

if __name__ == "__main__":
    main()
