#!/usr/bin/env python3
"""
重新建立 bronze.bpm_act_hi_taskinst 表
使用正確的 Nullable 時間欄位定義
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

def backup_existing_table(client):
    """備份現有表資料"""
    print("1. 備份現有表資料...")
    
    try:
        # 檢查現有表記錄數
        result = client.query("SELECT COUNT(*) FROM bronze.bpm_act_hi_taskinst")
        record_count = result.result_rows[0][0]
        print(f"   現有記錄數: {record_count:,}")
        
        if record_count > 0:
            # 建立備份表
            backup_sql = """
            CREATE TABLE bronze.bpm_act_hi_taskinst_backup
            ENGINE = MergeTree()
            ORDER BY ID_
            AS SELECT * FROM bronze.bpm_act_hi_taskinst
            """
            client.command(backup_sql)
            print("   ✅ 備份表建立完成")
            return True
        else:
            print("   ⚠️  現有表無資料，跳過備份")
            return True
            
    except Exception as e:
        print(f"   ❌ 備份失敗: {e}")
        return False

def recreate_taskinst_table(client):
    """重新建立 taskinst 表"""
    print("2. 重新建立 taskinst 表...")
    
    try:
        # 刪除現有表
        client.command("DROP TABLE IF EXISTS bronze.bpm_act_hi_taskinst")
        print("   舊表已刪除")
        
        # 建立新表（使用正確的 Nullable 定義）
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
            _batch_id String
        )
        ENGINE = ReplacingMergeTree(_sync_time)
        PARTITION BY toYYYYMM(START_TIME_)
        ORDER BY (PROC_INST_ID_, START_TIME_, ID_)
        SETTINGS index_granularity = 8192
        """
        
        client.command(create_sql)
        print("   ✅ 新表建立完成")
        
        # 檢查表結構
        structure = client.query("DESCRIBE bronze.bpm_act_hi_taskinst")
        print(f"   表結構: {len(structure.result_rows)} 個欄位")
        
        # 檢查關鍵時間欄位
        time_fields = ['START_TIME_', 'CLAIM_TIME_', 'END_TIME_']
        for row in structure.result_rows:
            column_name = row[0]
            column_type = row[1]
            if column_name in time_fields:
                nullable = "Nullable" in column_type
                print(f"   {column_name}: {column_type} {'✅' if nullable or column_name == 'START_TIME_' else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 表建立失敗: {e}")
        return False

def restore_data_from_backup(client):
    """從備份恢復資料"""
    print("3. 從備份恢復資料...")
    
    try:
        # 檢查備份表是否存在
        backup_check = client.query("""
        SELECT COUNT(*) 
        FROM system.tables 
        WHERE database = 'bronze' AND name = 'bpm_act_hi_taskinst_backup'
        """)
        
        if backup_check.result_rows[0][0] > 0:
            # 從備份恢復資料
            restore_sql = """
            INSERT INTO bronze.bpm_act_hi_taskinst
            SELECT 
                ID_, REV_, PROC_DEF_ID_, TASK_DEF_ID_, TASK_DEF_KEY_, 
                PROC_INST_ID_, EXECUTION_ID_, SCOPE_ID_, SUB_SCOPE_ID_, 
                SCOPE_TYPE_, SCOPE_DEFINITION_ID_, PROPAGATED_STAGE_INST_ID_,
                NAME_, PARENT_TASK_ID_, DESCRIPTION_, OWNER_, ASSIGNEE_,
                START_TIME_, CLAIM_TIME_, END_TIME_, DURATION_, DELETE_REASON_,
                PRIORITY_, DUE_DATE_, FORM_KEY_, CATEGORY_, TENANT_ID_,
                LAST_UPDATED_TIME_, _sync_time, _source_db, _batch_id
            FROM bronze.bpm_act_hi_taskinst_backup
            """
            
            client.command(restore_sql)
            
            # 檢查恢復結果
            result = client.query("SELECT COUNT(*) FROM bronze.bpm_act_hi_taskinst")
            record_count = result.result_rows[0][0]
            print(f"   ✅ 資料恢復完成: {record_count:,} 筆")
            
            # 清理備份表
            client.command("DROP TABLE bronze.bpm_act_hi_taskinst_backup")
            print("   備份表已清理")
            
            return True
        else:
            print("   ⚠️  無備份表，跳過資料恢復")
            return True
            
    except Exception as e:
        print(f"   ❌ 資料恢復失敗: {e}")
        return False

def test_table_queries(client):
    """測試表查詢功能"""
    print("4. 測試表查詢功能...")
    
    try:
        # 測試基本查詢
        basic_query = client.query("SELECT COUNT(*) FROM bronze.bpm_act_hi_taskinst")
        total_count = basic_query.result_rows[0][0]
        print(f"   總記錄數: {total_count:,}")
        
        # 測試時間欄位查詢
        time_query = client.query("""
        SELECT 
            COUNT(*) as total,
            COUNT(START_TIME_) as has_start_time,
            COUNT(CLAIM_TIME_) as has_claim_time,
            COUNT(END_TIME_) as has_end_time
        FROM bronze.bpm_act_hi_taskinst
        """)
        
        if time_query.result_rows:
            total, start_time, claim_time, end_time = time_query.result_rows[0]
            print(f"   時間欄位統計:")
            print(f"   - START_TIME_: {start_time:,}/{total:,} ({start_time/total*100:.1f}%)")
            print(f"   - CLAIM_TIME_: {claim_time:,}/{total:,} ({claim_time/total*100:.1f}%)")
            print(f"   - END_TIME_: {end_time:,}/{total:,} ({end_time/total*100:.1f}%)")
        
        # 測試範例查詢
        sample_query = client.query("""
        SELECT ID_, TASK_DEF_KEY_, START_TIME_, CLAIM_TIME_, END_TIME_
        FROM bronze.bpm_act_hi_taskinst
        LIMIT 3
        """)
        
        print(f"   範例資料:")
        for i, row in enumerate(sample_query.result_rows, 1):
            task_id, task_def, start_time, claim_time, end_time = row
            print(f"   {i}. {task_id[:8]}... | DEF: {task_def} | 開始: {start_time} | 認領: {claim_time} | 結束: {end_time}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 查詢測試失敗: {e}")
        return False

def main():
    """主執行函數"""
    try:
        print("🔧 重新建立 bronze.bpm_act_hi_taskinst 表")
        print("="*60)
        
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 執行重建流程
        if not backup_existing_table(client):
            return False
        
        if not recreate_taskinst_table(client):
            return False
        
        if not restore_data_from_backup(client):
            return False
        
        if not test_table_queries(client):
            return False
        
        print("\n✅ bronze.bpm_act_hi_taskinst 表重建完成")
        print("📋 修正內容:")
        print("   - CLAIM_TIME_ 改為 Nullable(DateTime)")
        print("   - END_TIME_ 改為 Nullable(DateTime)")
        print("   - 保持 START_TIME_ 為 DateTime (必填)")
        print("   - 資料完整恢復並可正常查詢")
        
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