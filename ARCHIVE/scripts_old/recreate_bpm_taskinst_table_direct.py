#!/usr/bin/env python3
"""
直接重新建立 bronze.bpm_act_hi_taskinst 表
跳過備份，直接重建並重新同步資料
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def recreate_taskinst_table_direct(client):
    """直接重新建立 taskinst 表"""
    print("🔧 直接重新建立 bronze.bpm_act_hi_taskinst 表")
    print("="*60)
    
    try:
        # 1. 刪除現有表
        print("1. 刪除現有表...")
        client.command("DROP TABLE IF EXISTS bronze.bpm_act_hi_taskinst")
        print("   ✅ 舊表已刪除")
        
        # 2. 建立新表（使用正確的 Nullable 定義）
        print("2. 建立新表...")
        create_sql = """
        CREATE TABLE bronze.bpm_act_hi_taskinst
        (
            ID_ String,
            REV_ Nullable(Int32),
            PROC_DEF_ID_ Nullable(String),
            TASK_DEF_ID_ Nullable(String),
            TASK_DEF_KEY_ Nullable(String),
            PROC_INST_ID_ Nullable(String),
            EXECUTION_ID_ Nullable(String),
            SCOPE_ID_ Nullable(String),
            SUB_SCOPE_ID_ Nullable(String),
            SCOPE_TYPE_ Nullable(String),
            SCOPE_DEFINITION_ID_ Nullable(String),
            PROPAGATED_STAGE_INST_ID_ Nullable(String),
            NAME_ Nullable(String),
            PARENT_TASK_ID_ Nullable(String),
            DESCRIPTION_ Nullable(String),
            OWNER_ Nullable(String),
            ASSIGNEE_ Nullable(String),
            START_TIME_ DateTime,
            CLAIM_TIME_ Nullable(DateTime),
            END_TIME_ Nullable(DateTime),
            DURATION_ Nullable(Decimal(38, 0)),
            DELETE_REASON_ Nullable(String),
            PRIORITY_ Nullable(Int32),
            DUE_DATE_ Nullable(DateTime),
            FORM_KEY_ Nullable(String),
            CATEGORY_ Nullable(String),
            TENANT_ID_ Nullable(String),
            LAST_UPDATED_TIME_ Nullable(DateTime64(7)),
            -- 同步 metadata
            _sync_time DateTime64(3) DEFAULT now64(3),
            _source_db LowCardinality(String) DEFAULT 'APP_SRV_BPM',
            _batch_id String DEFAULT ''
        )
        ENGINE = ReplacingMergeTree(_sync_time)
        PARTITION BY toYYYYMM(START_TIME_)
        ORDER BY (PROC_INST_ID_, START_TIME_, ID_)
        SETTINGS index_granularity = 8192, allow_nullable_key = 1
        """
        
        client.command(create_sql)
        print("   ✅ 新表建立完成")
        
        # 3. 檢查表結構
        print("3. 檢查表結構...")
        structure = client.query("DESCRIBE bronze.bpm_act_hi_taskinst")
        print(f"   表結構: {len(structure.result_rows)} 個欄位")
        
        # 檢查關鍵時間欄位
        time_fields = ['START_TIME_', 'CLAIM_TIME_', 'END_TIME_']
        for row in structure.result_rows:
            column_name = row[0]
            column_type = row[1]
            if column_name in time_fields:
                nullable = "Nullable" in column_type
                status = "✅" if nullable or column_name == 'START_TIME_' else "❌"
                print(f"   {column_name}: {column_type} {status}")
        
        # 4. 測試插入範例資料
        print("4. 測試插入範例資料...")
        test_insert_sql = """
        INSERT INTO bronze.bpm_act_hi_taskinst 
        (ID_, TASK_DEF_KEY_, PROC_INST_ID_, START_TIME_, CLAIM_TIME_, END_TIME_, _batch_id)
        VALUES 
        ('test-001', 'V1_TEST', 'proc-001', '2024-01-01 10:00:00', NULL, NULL, 'test-batch'),
        ('test-002', 'V2_TEST', 'proc-002', '2024-01-01 11:00:00', '2024-01-01 11:30:00', NULL, 'test-batch'),
        ('test-003', 'V3_TEST', 'proc-003', '2024-01-01 12:00:00', '2024-01-01 12:15:00', '2024-01-01 13:00:00', 'test-batch')
        """
        
        client.command(test_insert_sql)
        
        # 檢查插入結果
        result = client.query("SELECT COUNT(*) FROM bronze.bpm_act_hi_taskinst")
        record_count = result.result_rows[0][0]
        print(f"   ✅ 測試資料插入成功: {record_count} 筆")
        
        # 5. 測試查詢功能
        print("5. 測試查詢功能...")
        test_query = client.query("""
        SELECT ID_, TASK_DEF_KEY_, START_TIME_, CLAIM_TIME_, END_TIME_
        FROM bronze.bpm_act_hi_taskinst
        ORDER BY ID_
        """)
        
        print("   查詢結果:")
        for i, row in enumerate(test_query.result_rows, 1):
            task_id, task_def, start_time, claim_time, end_time = row
            print(f"   {i}. {task_id} | {task_def} | 開始: {start_time} | 認領: {claim_time} | 結束: {end_time}")
        
        # 6. 清理測試資料
        client.command("DELETE FROM bronze.bpm_act_hi_taskinst WHERE _batch_id = 'test-batch'")
        print("   測試資料已清理")
        
        return True
        
    except Exception as e:
        print(f"❌ 表重建失敗: {e}")
        return False

def show_sync_instructions(client):
    """顯示資料同步指示"""
    print("\n📋 後續資料同步指示:")
    print("="*60)
    
    print("1. 表結構已修正，可接受 NULL 值:")
    print("   - CLAIM_TIME_: Nullable(DateTime)")
    print("   - END_TIME_: Nullable(DateTime)")
    print("   - START_TIME_: DateTime (必填)")
    
    print("\n2. 建議的資料同步方式:")
    print("   - 使用現有的 ETL 流程重新同步 MSSQL 資料")
    print("   - 或手動執行 INSERT 語句載入資料")
    
    print("\n3. 驗證同步後的資料:")
    print("   - 檢查記錄數是否正確")
    print("   - 驗證時間欄位 NULL 值處理")
    print("   - 測試 MVIEW 查詢是否正常")

def main():
    """主執行函數"""
    try:
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 執行重建流程
        if not recreate_taskinst_table_direct(client):
            return False
        
        # 顯示後續指示
        show_sync_instructions(client)
        
        print("\n✅ bronze.bpm_act_hi_taskinst 表重建完成")
        print("⚠️  注意: 需要重新同步 MSSQL 資料")
        
        return True
        
    except Exception as e:
        print(f"❌ 執行過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)