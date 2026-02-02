import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\n比較資料總量:")
    
    # 1. ClickHouse Bronze Count
    try:
        ch_count = client.command("SELECT count() FROM bronze.bpm_act_hi_taskinst")
        print(f"ClickHouse (bronze.bpm_act_hi_taskinst): {ch_count:,}")
    except Exception as e:
        print(f"CH Error: {e}")

    # 2. MSSQL Count
    try:
        mssql_count = client.command("SELECT count(*) FROM jdbc('mssql_master', 'SELECT count(*) FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST')")
        print(f"MSSQL (ACT_HI_TASKINST): {mssql_count:,}")
    except Exception as e:
        print(f"MSSQL Error: {e}")
        
    print("\n")

if __name__ == "__main__":
    main()
