#!/usr/bin/env python3
"""
強制重建 bronze.bpm_act_hi_taskinst 表
解決欄位數量不匹配問題
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

def force_rebuild_taskinst(client):
    """強制重建 taskinst 表"""
    print("🔧 強制重建 bronze.bpm_act_hi_taskinst 表")
    print("="*50)
    
    try:
        # 1. 刪除現有表
        print("1. 刪除現有表...")
        client.command("DROP TABLE IF EXISTS bronze.bpm_act_hi_taskinst")
        print("   ✅ 舊表已刪除")
        
        # 2. 從 MSSQL 重新建立表
        print("2. 從 MSSQL 重新建立表...")
        create_sql = """
        CREATE TABLE bronze.bpm_act_hi_taskinst
        ENGINE = ReplacingMergeTree(_sync_time)
        ORDER BY (ID_)
        SETTINGS allow_nullable_key = 1
        AS SELECT *, now64(3) as _sync_time 
        FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST')
        """
        
        client.command(create_sql)
        print("   ✅ 表重建完成")
        
        # 3. 檢查結果
        result = client.query("SELECT COUNT(*) FROM bronze.bpm_act_hi_taskinst")
        record_count = result.result_rows[0][0]
        print(f"   📊 記錄數: {record_count:,}")
        
        # 4. 檢查表結構
        structure = client.query("DESCRIBE bronze.bpm_act_hi_taskinst")
        print(f"   📋 欄位數: {len(structure.result_rows)}")
        
        # 檢查關鍵時間欄位
        time_fields = ['START_TIME_', 'CLAIM_TIME_', 'END_TIME_']
        for row in structure.result_rows:
            column_name = row[0]
            column_type = row[1]
            if column_name in time_fields:
                nullable = "Nullable" in column_type
                status = "✅" if nullable or column_name == 'START_TIME_' else "❌"
                print(f"   {column_name}: {column_type} {status}")
        
        # 5. 測試查詢
        print("3. 測試查詢...")
        test_query = client.query("""
        SELECT ID_, TASK_DEF_KEY_, START_TIME_, CLAIM_TIME_, END_TIME_
        FROM bronze.bpm_act_hi_taskinst
        LIMIT 3
        """)
        
        print("   查詢結果:")
        for i, row in enumerate(test_query.result_rows, 1):
            task_id, task_def, start_time, claim_time, end_time = row
            print(f"   {i}. {task_id[:8]}... | {task_def} | 開始: {start_time} | 認領: {claim_time} | 結束: {end_time}")
        
        # 6. 更新 watermark
        print("4. 更新 watermark...")
        max_time_result = client.query("""
        SELECT MAX(LAST_UPDATED_TIME_) FROM bronze.bpm_act_hi_taskinst
        """)
        
        if max_time_result.result_rows and max_time_result.result_rows[0][0]:
            max_time = str(max_time_result.result_rows[0][0])
            
            watermark_sql = f"""
            INSERT INTO bronze._sync_watermark (table_name, last_sync_time, sync_time, row_count)
            VALUES ('bronze.bpm_act_hi_taskinst', '{max_time}', now64(3), {record_count})
            """
            client.command(watermark_sql)
            print(f"   ✅ Watermark 已更新: {max_time}")
        
        return True
        
    except Exception as e:
        print(f"❌ 重建失敗: {e}")
        return False

def main():
    """主執行函數"""
    try:
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 執行重建
        if not force_rebuild_taskinst(client):
            return False
        
        print("\n✅ bronze.bpm_act_hi_taskinst 表強制重建完成")
        print("📋 修正內容:")
        print("   - 從 MSSQL 重新同步所有資料")
        print("   - 自動匹配正確的欄位結構")
        print("   - 更新 watermark 記錄")
        
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