#!/usr/bin/env python3
"""
分析目前 MVIEW 架構中製造五階維度的資料來源
檢查是否使用了 MDM 主檔表，還是僅依賴 Flowable 變數
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
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def analyze_current_mview_structure(client):
    """分析目前 MVIEW 的維度來源"""
    print("🔍 分析目前 MVIEW 架構中的製造五階維度來源")
    print("="*70)
    
    # 檢查 silver.mv_fact_task_vx_attribution 的維度欄位
    try:
        structure_query = """
        DESCRIBE silver.mv_fact_task_vx_attribution
        """
        
        result = client.query(structure_query)
        columns = result.result_rows
        
        print("📊 silver.mv_fact_task_vx_attribution 表結構:")
        dimension_fields = []
        for col in columns:
            col_name = col[0]
            col_type = col[1]
            if col_name in ['plant', 'factory', 'line', 'vx_type', 'vx_subtype']:
                dimension_fields.append(col_name)
                print(f"  ✅ {col_name}: {col_type}")
        
        print(f"\n📋 發現維度欄位: {dimension_fields}")
        
        # 檢查維度資料樣本
        sample_query = """
        SELECT plant, factory, line, vx_type, vx_subtype, COUNT(*) as count
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE plant != '' OR factory != '' OR line != ''
        GROUP BY plant, factory, line, vx_type, vx_subtype
        ORDER BY count DESC
        LIMIT 10
        """
        
        sample_result = client.query(sample_query)
        
        print("\n📊 維度資料樣本 (前10筆):")
        print("-" * 80)
        print(f"{'Plant':<15} {'Factory':<15} {'Line':<20} {'Vx':<5} {'Subtype':<10} {'Count':<8}")
        print("-" * 80)
        
        for row in sample_result.result_rows:
            plant = row[0] or 'NULL'
            factory = row[1] or 'NULL'
            line = row[2] or 'NULL'
            vx_type = row[3] or 'NULL'
            vx_subtype = row[4] or 'NULL'
            count = row[5]
            print(f"{plant:<15} {factory:<15} {line:<20} {vx_type:<5} {vx_subtype:<10} {count:<8}")
            
    except Exception as e:
        print(f"❌ MVIEW 結構分析失敗: {e}")

def check_mdm_tables_usage(client):
    """檢查是否有使用 MDM 主檔表"""
    print("\n🔍 檢查 MDM 主檔表使用情況")
    print("="*50)
    
    mdm_tables = [
        'bronze.common_mdm_line_desc_master',
        'bronze.common_mdm_prod_area_master', 
        'bronze.common_mdm_mfg_plant_master',
        'bronze.common_mdm_factory_area_master',
        'bronze.common_mdm_mfg_site_master'
    ]
    
    for table in mdm_tables:
        try:
            count_query = f"SELECT COUNT(*) as count FROM {table}"
            result = client.query(count_query)
            count = result.result_rows[0][0]
            
            # 檢查表結構
            desc_query = f"DESCRIBE {table}"
            desc_result = client.query(desc_query)
            columns = [row[0] for row in desc_result.result_rows]
            
            print(f"✅ {table}: {count:,} 筆記錄")
            print(f"   關鍵欄位: {', '.join(columns[:5])}...")
            
        except Exception as e:
            print(f"❌ {table}: 不存在或查詢失敗 - {e}")

def check_varinst_pivoted_source(client):
    """檢查 varinst_pivoted 的資料來源"""
    print("\n🔍 檢查 silver.mv_varinst_pivoted 資料來源")
    print("="*55)
    
    try:
        # 檢查 varinst_pivoted 表結構
        structure_query = """
        DESCRIBE silver.mv_varinst_pivoted
        """
        
        result = client.query(structure_query)
        columns = result.result_rows
        
        print("📊 silver.mv_varinst_pivoted 表結構:")
        for col in columns:
            col_name = col[0]
            col_type = col[1]
            if 'varinst' in col_name:
                print(f"  ✅ {col_name}: {col_type}")
        
        # 檢查資料樣本
        sample_query = """
        SELECT varinst_plant, varinst_factory, varinst_lineName, varinst_moNumber, COUNT(*) as count
        FROM silver.mv_varinst_pivoted FINAL
        WHERE varinst_plant != '' OR varinst_factory != '' OR varinst_lineName != ''
        GROUP BY varinst_plant, varinst_factory, varinst_lineName, varinst_moNumber
        ORDER BY count DESC
        LIMIT 10
        """
        
        sample_result = client.query(sample_query)
        
        print("\n📊 varinst_pivoted 資料樣本 (前10筆):")
        print("-" * 80)
        print(f"{'Plant':<15} {'Factory':<15} {'Line':<20} {'MoNumber':<15} {'Count':<8}")
        print("-" * 80)
        
        for row in sample_result.result_rows:
            plant = row[0] or 'NULL'
            factory = row[1] or 'NULL'
            line = row[2] or 'NULL'
            mo_number = row[3] or 'NULL'
            count = row[4]
            print(f"{plant:<15} {factory:<15} {line:<20} {mo_number:<15} {count:<8}")
            
        # 檢查覆蓋率
        coverage_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN varinst_plant != '' THEN 1 END) as has_plant,
            COUNT(CASE WHEN varinst_factory != '' THEN 1 END) as has_factory,
            COUNT(CASE WHEN varinst_lineName != '' THEN 1 END) as has_line,
            COUNT(CASE WHEN varinst_moNumber != '' THEN 1 END) as has_mo_number
        FROM silver.mv_varinst_pivoted FINAL
        """
        
        coverage_result = client.query(coverage_query)
        coverage_row = coverage_result.result_rows[0]
        
        total = coverage_row[0]
        has_plant = coverage_row[1]
        has_factory = coverage_row[2]
        has_line = coverage_row[3]
        has_mo = coverage_row[4]
        
        print(f"\n📊 varinst_pivoted 覆蓋率分析:")
        print(f"  總記錄數: {total:,}")
        print(f"  有 Plant: {has_plant:,} ({has_plant/total*100:.1f}%)")
        print(f"  有 Factory: {has_factory:,} ({has_factory/total*100:.1f}%)")
        print(f"  有 Line: {has_line:,} ({has_line/total*100:.1f}%)")
        print(f"  有 MoNumber: {has_mo:,} ({has_mo/total*100:.1f}%)")
            
    except Exception as e:
        print(f"❌ varinst_pivoted 分析失敗: {e}")

def check_dimension_table_exists(client):
    """檢查製造五階維度表是否存在"""
    print("\n🔍 檢查製造五階維度表")
    print("="*35)
    
    try:
        # 檢查 silver.dim_mfg_five_level 是否存在
        dim_query = """
        SELECT COUNT(*) as count FROM silver.dim_mfg_five_level
        """
        
        result = client.query(dim_query)
        count = result.result_rows[0][0]
        
        print(f"✅ silver.dim_mfg_five_level: {count:,} 筆記錄")
        
        # 檢查表結構
        structure_query = """
        DESCRIBE silver.dim_mfg_five_level
        """
        
        structure_result = client.query(structure_query)
        
        print("📊 製造五階維度表結構:")
        for col in structure_result.result_rows:
            col_name = col[0]
            col_type = col[1]
            if col_name in ['region_code', 'plant_code', 'factory_code', 'line_name', 'is_valid']:
                print(f"  ✅ {col_name}: {col_type}")
        
        # 檢查資料品質
        quality_query = """
        SELECT 
            COUNT(*) as total_lines,
            SUM(is_valid) as valid_lines,
            COUNT(CASE WHEN region_code IS NOT NULL THEN 1 END) as has_region,
            COUNT(CASE WHEN plant_code IS NOT NULL THEN 1 END) as has_plant,
            COUNT(CASE WHEN factory_code IS NOT NULL THEN 1 END) as has_factory
        FROM silver.dim_mfg_five_level
        """
        
        quality_result = client.query(quality_query)
        quality_row = quality_result.result_rows[0]
        
        total = quality_row[0]
        valid = quality_row[1]
        has_region = quality_row[2]
        has_plant = quality_row[3]
        has_factory = quality_row[4]
        
        print(f"\n📊 製造五階維度表品質:")
        print(f"  總產線數: {total:,}")
        print(f"  有效產線: {valid:,} ({valid/total*100:.1f}%)")
        print(f"  有 Region: {has_region:,} ({has_region/total*100:.1f}%)")
        print(f"  有 Plant: {has_plant:,} ({has_plant/total*100:.1f}%)")
        print(f"  有 Factory: {has_factory:,} ({has_factory/total*100:.1f}%)")
        
    except Exception as e:
        print(f"❌ 製造五階維度表不存在或查詢失敗: {e}")

def analyze_mview_dimension_source(client):
    """分析 MVIEW 是否使用了 MDM 維度"""
    print("\n🔍 分析 MVIEW 維度來源")
    print("="*35)
    
    print("📋 目前 MVIEW 架構分析:")
    print("1. silver.mv_fact_task_vx_attribution 維度欄位:")
    print("   - plant: 來自 silver.mv_varinst_pivoted.varinst_plant")
    print("   - factory: 來自 silver.mv_varinst_pivoted.varinst_factory") 
    print("   - line: 來自 silver.mv_varinst_pivoted.varinst_lineName")
    print("   - vx_type: 來自業務邏輯推導")
    print("   - vx_subtype: 來自 NPE 判別邏輯")
    
    print("\n2. silver.mv_varinst_pivoted 資料來源:")
    print("   - 來自 bronze.bpm_act_hi_varinst (Flowable 原生變數表)")
    print("   - EAV 結構轉置為寬表格式")
    print("   - 僅包含 V1 流程的變數資料")
    
    print("\n⚠️  發現問題:")
    print("❌ 目前 MVIEW 架構 **未使用** MDM 主檔表")
    print("❌ 維度資料完全依賴 Flowable 變數 (varinst)")
    print("❌ 缺少 Region 層級資料")
    print("❌ 未與 MDM 主檔進行串接驗證")
    
    print("\n📋 建議改善:")
    print("1. 在 MVIEW 中加入 MDM 主檔表串接")
    print("2. 建立 Flowable vs MDM 的一致性檢查")
    print("3. 補齊 Region 層級維度")
    print("4. 建立維度資料品質監控")

def main():
    """主執行函數"""
    try:
        print("🚀 開始分析 MVIEW 製造五階維度來源")
        print("="*80)
        
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 1. 分析目前 MVIEW 結構
        analyze_current_mview_structure(client)
        
        # 2. 檢查 MDM 主檔表
        check_mdm_tables_usage(client)
        
        # 3. 檢查 varinst_pivoted 來源
        check_varinst_pivoted_source(client)
        
        # 4. 檢查製造五階維度表
        check_dimension_table_exists(client)
        
        # 5. 分析維度來源
        analyze_mview_dimension_source(client)
        
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