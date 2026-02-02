#!/usr/bin/env python3
"""
恢復缺失的表
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔧 恢復缺失的 bronze.bpm_act_hi_procinst 表")
    
    try:
        # 檢查備份表是否存在
        backup_exists = client.command("EXISTS TABLE bronze.bpm_act_hi_procinst_backup")
        
        if backup_exists:
            backup_count = client.command("SELECT count(*) FROM bronze.bpm_act_hi_procinst_backup")
            print(f"✅ 找到備份表: {backup_count:,} 筆資料")
            
            # 重命名備份表為正式表
            print("🔄 重命名備份表為正式表...")
            client.command("RENAME TABLE bronze.bpm_act_hi_procinst_backup TO bronze.bpm_act_hi_procinst")
            
            # 驗證
            new_count = client.command("SELECT count(*) FROM bronze.bpm_act_hi_procinst")
            print(f"✅ 恢復成功: bronze.bpm_act_hi_procinst 現有 {new_count:,} 筆資料")
            
        else:
            print("❌ 找不到備份表，需要重新同步")
            
    except Exception as e:
        print(f"❌ 恢復失敗: {e}")

if __name__ == "__main__":
    main()