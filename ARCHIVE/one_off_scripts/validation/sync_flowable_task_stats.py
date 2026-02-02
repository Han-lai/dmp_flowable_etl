#!/usr/bin/env python3
"""
同步 FlowableTaskStats 表 (增加 timeout + 分批)
從 MSSQL APP_SRV_COMMON.dbo.FlowableTaskStats 同步到 ClickHouse bronze.common_flowable_task_stats
"""

import clickhouse_connect
from datetime import datetime

# ClickHouse 連線設定 (增加 timeout)
CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 1800,  # 30 分鐘
    "connect_timeout": 60
}

def main():
    print("=" * 60)
    print("同步 FlowableTaskStats 表 (增加 timeout)")
    print("=" * 60)
    print(f"開始時間: {datetime.now()}")
    
    # 連線 ClickHouse
    print("\n📡 連線 ClickHouse (timeout=30min)...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    print("✅ ClickHouse 連線成功")
    
    # 設定長 timeout
    print("\n⚙️ 設定 ClickHouse 長 timeout...")
    client.command("SET send_timeout = 1800")
    client.command("SET receive_timeout = 1800")
    client.command("SET http_receive_timeout = 1800")
    client.command("SET http_send_timeout = 1800")
    
    # 先檢查 MSSQL 連線和資料量
    print("\n📊 檢查 MSSQL 來源資料量...")
    try:
        count_result = client.query("""
            SELECT * FROM jdbc('mssql_master', 
                'SELECT COUNT(*) as cnt FROM APP_SRV_COMMON.dbo.FlowableTaskStats')
        """)
        mssql_count = count_result.result_rows[0][0]
        print(f"  MSSQL 來源: {mssql_count:,} 筆")
        print(f"  預估同步時間: {mssql_count // 10000} ~ {mssql_count // 5000} 分鐘")
    except Exception as e:
        print(f"  ⚠️ 無法取得 MSSQL 資料量: {e}")
        mssql_count = 0
    
    # 同步資料
    print("\n🔄 開始同步 (請耐心等待)...")
    print("  來源: APP_SRV_COMMON.dbo.FlowableTaskStats")
    print("  目標: bronze.common_flowable_task_stats")
    
    start_time = datetime.now()
    
    try:
        # 刪除舊表
        client.command("DROP TABLE IF EXISTS bronze.common_flowable_task_stats")
        
        # 建立新表並同步資料 (使用較大的 timeout)
        sync_sql = """
        CREATE TABLE bronze.common_flowable_task_stats
        ENGINE = ReplacingMergeTree(_sync_time)
        ORDER BY (Id)
        SETTINGS allow_nullable_key = 1
        AS SELECT *, now64(3) as _sync_time 
        FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.FlowableTaskStats')
        SETTINGS 
            max_execution_time = 1800,
            send_timeout = 1800,
            receive_timeout = 1800
        """
        
        client.command(sync_sql)
        
        # 取得同步結果
        new_count = client.command("SELECT count() FROM bronze.common_flowable_task_stats")
        duration = (datetime.now() - start_time).total_seconds()
        
        print(f"\n✅ 同步完成!")
        print(f"  同步筆數: {new_count:,}")
        print(f"  耗時: {duration:.1f} 秒 ({duration/60:.1f} 分鐘)")
        print(f"  速度: {new_count / duration:.0f} 筆/秒")
        
        # 檢查資料樣本
        print("\n📋 資料樣本 (TaskStatus 分布):")
        result = client.query("""
            SELECT 
                TaskStatus, 
                count() as cnt,
                round(count() * 100.0 / sum(count()) OVER (), 2) as pct
            FROM bronze.common_flowable_task_stats
            GROUP BY TaskStatus
            ORDER BY cnt DESC
        """)
        for row in result.result_rows:
            print(f"  {row[0]}: {row[1]:,} ({row[2]}%)")
        
        # Vx 類型分布
        print("\n📋 Vx 類型分布:")
        result = client.query("""
            SELECT 
                CASE 
                    WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
                    WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
                    WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
                    ELSE 'Other'
                END AS vx_type,
                count() as cnt
            FROM bronze.common_flowable_task_stats
            GROUP BY vx_type
            ORDER BY cnt DESC
        """)
        for row in result.result_rows:
            print(f"  {row[0]}: {row[1]:,}")
            
    except Exception as e:
        print(f"\n❌ 同步失敗: {e}")
        print("\n💡 建議:")
        print("  1. 可能需要在 ClickHouse server 端增加 timeout 設定")
        print("  2. 或使用分批同步方法")
        return
    
    print("\n" + "=" * 60)
    print(f"完成時間: {datetime.now()}")
    print("=" * 60)

if __name__ == "__main__":
    main()
