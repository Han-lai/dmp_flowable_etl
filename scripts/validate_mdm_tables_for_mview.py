#!/usr/bin/env python3
"""
驗證 MDM 主檔表是否可支援 MVIEW 製造五階維度重構
檢查表結構、資料品質、與 Flowable 的對應關係
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect
from datetime import datetime
import pandas as pd

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

def validate_mdm_table_structure(client):
    """驗證 MDM 主檔表結構和資料品質"""
    print("🔍 驗證 MDM 主檔表結構和資料品質")
    print("="*60)
    
    mdm_tables = {
        'bronze.common_mdm_mfg_site_master': 'Region 層級',
        'bronze.common_mdm_factory_area_master': 'Plant 層級', 
        'bronze.common_mdm_mfg_plant_master': 'Factory 層級',
        'bronze.common_mdm_line_desc_master': 'Line 層級'
    }
    
    table_info = {}
    
    for table, level in mdm_tables.items():
        try:
            print(f"\n📊 {table} ({level})")
            print("-" * 50)
            
            # 檢查表結構
            desc_query = f"DESCRIBE {table}"
            desc_result = client.query(desc_query)
            columns = [row[0] for row in desc_result.result_rows]
            
            # 檢查記錄數
            count_query = f"SELECT COUNT(*) FROM {table}"
            count_result = client.query(count_query)
            record_count = count_result.result_rows[0][0]
            
            # 檢查關鍵欄位樣本
            if 'mfg_site_master' in table:
                sample_query = f"""
                SELECT MFG_SITE, MFG_SITE_DESC, COUNT(*) as cnt
                FROM {table}
                GROUP BY MFG_SITE, MFG_SITE_DESC
                ORDER BY cnt DESC
                LIMIT 5
                """
            elif 'factory_area_master' in table:
                sample_query = f"""
                SELECT FACTORY, MFG_SITE, COUNTRY, VALID, COUNT(*) as cnt
                FROM {table}
                WHERE VALID = '1'
                GROUP BY FACTORY, MFG_SITE, COUNTRY, VALID
                ORDER BY cnt DESC
                LIMIT 5
                """
            elif 'mfg_plant_master' in table:
                sample_query = f"""
                SELECT MFG_PLANT_CODE, MFG_PLANT_DESC, FACTORY, VALIDITY, COUNT(*) as cnt
                FROM {table}
                WHERE VALIDITY = 'Y'
                GROUP BY MFG_PLANT_CODE, MFG_PLANT_DESC, FACTORY, VALIDITY
                ORDER BY cnt DESC
                LIMIT 5
                """
            elif 'line_desc_master' in table:
                sample_query = f"""
                SELECT LINE_NAME, LINE_DESC, PROD_AREA_ID, VALID_FLAG, COUNT(*) as cnt
                FROM {table}
                WHERE VALID_FLAG = 'Y'
                GROUP BY LINE_NAME, LINE_DESC, PROD_AREA_ID, VALID_FLAG
                ORDER BY cnt DESC
                LIMIT 5
                """
            
            sample_result = client.query(sample_query)
            
            table_info[table] = {
                'level': level,
                'columns': columns,
                'record_count': record_count,
                'sample_data': sample_result.result_rows
            }
            
            print(f"✅ 記錄數: {record_count:,}")
            print(f"✅ 欄位數: {len(columns)}")
            print(f"✅ 關鍵欄位: {', '.join(columns[:8])}...")
            
            print("📋 資料樣本:")
            for i, row in enumerate(sample_result.result_rows[:3]):
                print(f"  {i+1}. {row}")
                
        except Exception as e:
            print(f"❌ {table} 驗證失敗: {e}")
            table_info[table] = {'error': str(e)}
    
    return table_info

def validate_flowable_mdm_mapping(client):
    """驗證 Flowable 與 MDM 的對應關係"""
    print("\n🔍 驗證 Flowable 與 MDM 的對應關係")
    print("="*50)
    
    try:
        # 檢查 Flowable 變數中的維度值與 MDM 的對應
        mapping_query = """
        WITH flowable_dims AS (
            SELECT DISTINCT
                varinst_plant,
                varinst_factory,
                varinst_lineName,
                COUNT(*) as flowable_count
            FROM silver.mv_varinst_pivoted
            WHERE varinst_plant != '' OR varinst_factory != '' OR varinst_lineName != ''
            GROUP BY varinst_plant, varinst_factory, varinst_lineName
            ORDER BY flowable_count DESC
            LIMIT 20
        ),
        mdm_lines AS (
            SELECT DISTINCT
                l.LINE_NAME,
                p.FACTORY as factory_code,
                mp.MFG_PLANT_CODE as plant_code
            FROM bronze.common_mdm_line_desc_master l
            LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
            LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY
            WHERE l.VALID_FLAG = 'Y'
        )
        SELECT 
            f.varinst_plant,
            f.varinst_factory,
            f.varinst_lineName,
            f.flowable_count,
            CASE WHEN m.LINE_NAME IS NOT NULL THEN 'MATCHED' ELSE 'NOT_MATCHED' END as mdm_match_status,
            m.plant_code as mdm_plant,
            m.factory_code as mdm_factory
        FROM flowable_dims f
        LEFT JOIN mdm_lines m ON f.varinst_lineName = m.LINE_NAME
        ORDER BY f.flowable_count DESC
        """
        
        mapping_result = client.query(mapping_query)
        
        print("📊 Flowable vs MDM 對應分析 (前20筆):")
        print("-" * 100)
        print(f"{'Flowable Plant':<15} {'Flowable Factory':<15} {'Flowable Line':<20} {'Count':<8} {'MDM Match':<12} {'MDM Plant':<12} {'MDM Factory':<12}")
        print("-" * 100)
        
        matched_count = 0
        total_count = 0
        
        for row in mapping_result.result_rows:
            f_plant = row[0] or 'NULL'
            f_factory = row[1] or 'NULL'
            f_line = row[2] or 'NULL'
            count = row[3]
            match_status = row[4]
            mdm_plant = row[5] or 'NULL'
            mdm_factory = row[6] or 'NULL'
            
            if match_status == 'MATCHED':
                matched_count += count
            total_count += count
            
            print(f"{f_plant:<15} {f_factory:<15} {f_line:<20} {count:<8} {match_status:<12} {mdm_plant:<12} {mdm_factory:<12}")
        
        match_rate = (matched_count / total_count * 100) if total_count > 0 else 0
        print(f"\n📈 對應成功率: {match_rate:.1f}% ({matched_count:,}/{total_count:,})")
        
        return match_rate
        
    except Exception as e:
        print(f"❌ Flowable vs MDM 對應驗證失敗: {e}")
        return 0

def validate_business_key_mapping(client):
    """驗證 Business Key 與維度的對應關係"""
    print("\n🔍 驗證 Business Key 與維度的對應關係")
    print("="*50)
    
    try:
        # 檢查 Business Key 是否包含維度資訊
        business_key_query = """
        SELECT 
            p.BUSINESS_KEY_,
            v.varinst_plant,
            v.varinst_factory,
            v.varinst_lineName,
            COUNT(*) as count
        FROM bronze.bpm_act_hi_procinst p
        LEFT JOIN silver.mv_varinst_pivoted v ON p.PROC_INST_ID_ = v.PROC_INST_ID_
        WHERE p.BUSINESS_KEY_ IS NOT NULL AND p.BUSINESS_KEY_ != ''
        GROUP BY p.BUSINESS_KEY_, v.varinst_plant, v.varinst_factory, v.varinst_lineName
        ORDER BY count DESC
        LIMIT 10
        """
        
        bk_result = client.query(business_key_query)
        
        print("📊 Business Key 與維度關係樣本:")
        print("-" * 80)
        print(f"{'Business Key':<30} {'Plant':<10} {'Factory':<10} {'Line':<15} {'Count':<8}")
        print("-" * 80)
        
        for row in bk_result.result_rows:
            bk = row[0] or 'NULL'
            plant = row[1] or 'NULL'
            factory = row[2] or 'NULL'
            line = row[3] or 'NULL'
            count = row[4]
            
            # 截斷過長的 Business Key
            if len(bk) > 28:
                bk = bk[:25] + "..."
                
            print(f"{bk:<30} {plant:<10} {factory:<10} {line:<15} {count:<8}")
            
    except Exception as e:
        print(f"❌ Business Key 對應驗證失敗: {e}")

def analyze_vx_dimension_coverage(client):
    """分析不同 Vx 類型的維度覆蓋率"""
    print("\n🔍 分析不同 Vx 類型的維度覆蓋率")
    print("="*50)
    
    try:
        vx_coverage_query = """
        SELECT 
            vx_type,
            COUNT(*) as total_tasks,
            COUNT(CASE WHEN plant != '' THEN 1 END) as has_plant,
            COUNT(CASE WHEN factory != '' THEN 1 END) as has_factory,
            COUNT(CASE WHEN line != '' THEN 1 END) as has_line,
            round(COUNT(CASE WHEN plant != '' THEN 1 END) * 100.0 / COUNT(*), 2) as plant_coverage,
            round(COUNT(CASE WHEN factory != '' THEN 1 END) * 100.0 / COUNT(*), 2) as factory_coverage,
            round(COUNT(CASE WHEN line != '' THEN 1 END) * 100.0 / COUNT(*), 2) as line_coverage
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE vx_type IN ('V1', 'V2', 'V3')
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        coverage_result = client.query(vx_coverage_query)
        
        print("📊 各 Vx 類型維度覆蓋率:")
        print("-" * 80)
        print(f"{'Vx Type':<8} {'Total Tasks':<12} {'Plant %':<10} {'Factory %':<12} {'Line %':<10}")
        print("-" * 80)
        
        for row in coverage_result.result_rows:
            vx_type = row[0]
            total = row[1]
            plant_pct = row[5]
            factory_pct = row[6]
            line_pct = row[7]
            
            print(f"{vx_type:<8} {total:<12,} {plant_pct:<10}% {factory_pct:<12}% {line_pct:<10}%")
            
    except Exception as e:
        print(f"❌ Vx 維度覆蓋率分析失敗: {e}")

def main():
    """主執行函數"""
    try:
        print("🚀 開始驗證 MDM 主檔表支援 MVIEW 製造五階維度")
        print("="*80)
        
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 1. 驗證 MDM 表結構和資料品質
        table_info = validate_mdm_table_structure(client)
        
        # 2. 驗證 Flowable vs MDM 對應關係
        match_rate = validate_flowable_mdm_mapping(client)
        
        # 3. 驗證 Business Key 對應
        validate_business_key_mapping(client)
        
        # 4. 分析 Vx 維度覆蓋率
        analyze_vx_dimension_coverage(client)
        
        # 5. 總結驗證結果
        print("\n" + "="*80)
        print("📋 MDM 表驗證總結")
        print("="*80)
        
        for table, info in table_info.items():
            if 'error' not in info:
                print(f"✅ {info['level']}: {table} - {info['record_count']:,} 筆記錄")
            else:
                print(f"❌ {table}: {info['error']}")
        
        print(f"\n📈 Flowable vs MDM 對應成功率: {match_rate:.1f}%")
        
        if match_rate > 70:
            print("✅ MDM 表可支援 MVIEW 製造五階維度重構")
        else:
            print("⚠️ MDM 表對應率偏低，需要額外的對應邏輯")
        
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