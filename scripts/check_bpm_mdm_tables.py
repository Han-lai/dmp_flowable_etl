#!/usr/bin/env python3
"""
檢查 BPM 和 MDM 相關表結構
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

def check_bpm_tables(client):
    """檢查 BPM 相關表"""
    print("🔍 檢查 BPM 相關表...")
    print("="*50)
    
    bpm_tables = [
        'bronze.bpm_act_hi_taskinst',
        'bronze.bpm_act_hi_procinst', 
        'bronze.bpm_act_hi_varinst'
    ]
    
    for table in bpm_tables:
        try:
            result = client.query(f'SELECT COUNT(*) FROM {table}')
            count = result.result_rows[0][0]
            print(f'✅ {table}: {count:,} 筆')
            
            # 檢查關鍵欄位
            if 'taskinst' in table:
                sample = client.query(f'SELECT ID_, TASK_DEF_KEY_, ASSIGNEE_, START_TIME_, END_TIME_ FROM {table} LIMIT 3')
                print(f'   範例資料: {len(sample.result_rows)} 筆')
                
            elif 'procinst' in table:
                sample = client.query(f'SELECT PROC_INST_ID_, BUSINESS_KEY_, NAME_ FROM {table} LIMIT 3')
                print(f'   範例資料: {len(sample.result_rows)} 筆')
                
            elif 'varinst' in table:
                sample = client.query(f'SELECT PROC_INST_ID_, NAME_, TEXT_ FROM {table} WHERE NAME_ IN (\'plant\', \'factory\', \'lineName\') LIMIT 5')
                print(f'   製造維度變數: {len(sample.result_rows)} 筆')
                
        except Exception as e:
            print(f'❌ {table}: {e}')

def check_mdm_tables(client):
    """檢查 MDM 相關表"""
    print("\n🔍 檢查 MDM 相關表...")
    print("="*50)
    
    mdm_tables = [
        ('bronze.common_mdm_mfg_site_master', 'Region'),
        ('bronze.common_mdm_factory_area_master', 'Plant'),
        ('bronze.common_mdm_mfg_plant_master', 'Factory'), 
        ('bronze.common_mdm_line_desc_master', 'Line')
    ]
    
    for table, level in mdm_tables:
        try:
            result = client.query(f'SELECT COUNT(*) FROM {table}')
            count = result.result_rows[0][0]
            print(f'✅ {table} ({level}): {count:,} 筆')
            
            # 檢查表結構
            structure = client.query(f'DESCRIBE {table}')
            columns = [row[0] for row in structure.result_rows]
            print(f'   欄位: {", ".join(columns[:5])}{"..." if len(columns) > 5 else ""}')
            
        except Exception as e:
            print(f'❌ {table}: {e}')

def check_silver_integration(client):
    """檢查 Silver 層整合表"""
    print("\n🔍 檢查 Silver 層整合表...")
    print("="*50)
    
    silver_tables = [
        'silver.mv_varinst_pivoted',
        'silver.dim_mfg_five_level'
    ]
    
    for table in silver_tables:
        try:
            result = client.query(f'SELECT COUNT(*) FROM {table}')
            count = result.result_rows[0][0]
            print(f'✅ {table}: {count:,} 筆')
            
            if 'varinst_pivoted' in table:
                # 檢查製造維度欄位
                sample = client.query(f'SELECT varinst_plant, varinst_factory, varinst_lineName FROM {table} WHERE varinst_plant IS NOT NULL LIMIT 3')
                print(f'   有製造維度的記錄: {len(sample.result_rows)} 筆範例')
                
            elif 'dim_mfg_five_level' in table:
                # 檢查維度完整性
                sample = client.query(f'SELECT region_code, plant_code, factory_code, line_name FROM {table} LIMIT 3')
                print(f'   五階維度範例: {len(sample.result_rows)} 筆')
                
        except Exception as e:
            print(f'❌ {table}: {e}')

def main():
    """主執行函數"""
    try:
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 檢查各類表
        check_bpm_tables(client)
        check_mdm_tables(client)
        check_silver_integration(client)
        
        print("\n✅ 表結構檢查完成")
        
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