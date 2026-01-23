#!/usr/bin/env python3
"""
檢查 MDM 整合 MVIEW 當前狀態
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect

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

def check_mview_status(client):
    """檢查 MVIEW 狀態"""
    print("🔍 檢查 MDM 整合 MVIEW 狀態")
    print("="*50)
    
    try:
        # 1. 檢查表是否存在
        print("1. 檢查表存在性...")
        
        tables_result = client.query("""
        SELECT name, engine, total_rows, total_bytes
        FROM system.tables 
        WHERE database = 'silver' 
          AND name LIKE '%attribution%'
        ORDER BY name
        """)
        
        print("   現有相關表:")
        for row in tables_result.result_rows:
            name, engine, rows, bytes_size = row
            size_mb = bytes_size / 1024 / 1024 if bytes_size else 0
            print(f"   - {name}: {engine}, {rows:,} 筆, {size_mb:.1f} MB")
        
        # 2. 檢查 MDM 測試表
        print("\n2. 檢查 MDM 測試表詳細資訊...")
        
        try:
            mdm_result = client.query("SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution_mdm")
            record_count = mdm_result.result_rows[0][0]
            if record_count > 0:
                print(f"   ✅ MDM 測試表記錄數: {record_count:,}")
            else:
                print(f"   ⚠️  MDM 測試表存在但無資料: {record_count}")
                return True
            
            # 檢查維度覆蓋率
            coverage_result = client.query("""
            SELECT 
                vx_type,
                COUNT(*) as total,
                round(COUNT(CASE WHEN region_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as region_pct,
                round(COUNT(CASE WHEN plant_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as plant_pct,
                round(COUNT(CASE WHEN factory_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as factory_pct,
                round(COUNT(CASE WHEN line_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as line_pct
            FROM silver.mv_fact_task_vx_attribution_mdm FINAL
            WHERE vx_type IN ('V1', 'V2', 'V3')
            GROUP BY vx_type
            ORDER BY vx_type
            """)
            
            print("   📊 維度覆蓋率:")
            print("   Vx   | Region% | Plant% | Factory% | Line%")
            print("   " + "="*40)
            for row in coverage_result.result_rows:
                vx, total, region_pct, plant_pct, factory_pct, line_pct = row
                print(f"   {vx:<4} | {region_pct:<7}% | {plant_pct:<6}% | {factory_pct:<8}% | {line_pct:<5}%")
            
            # 檢查資料來源分布
            source_result = client.query("""
            SELECT 
                dimension_source,
                COUNT(*) as count,
                round(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution_mdm FINAL), 2) as percentage
            FROM silver.mv_fact_task_vx_attribution_mdm FINAL
            GROUP BY dimension_source
            ORDER BY count DESC
            """)
            
            print("\n   📊 維度資料來源分布:")
            for row in source_result.result_rows:
                source, count, pct = row
                print(f"   {source}: {count:,} ({pct}%)")
            
        except Exception as e:
            print(f"   ❌ MDM 測試表不存在或查詢失敗: {e}")
        
        # 3. 檢查原版表對比
        print("\n3. 與原版表對比...")
        
        try:
            original_result = client.query("SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution")
            original_count = original_result.result_rows[0][0]
            print(f"   📊 原版表記錄數: {original_count:,}")
            
            if 'record_count' in locals():
                diff = record_count - original_count
                print(f"   📊 記錄數差異: {diff:+,}")
            
        except Exception as e:
            print(f"   ❌ 原版表查詢失敗: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 檢查過程發生錯誤: {e}")
        return False

def main():
    """主執行函數"""
    try:
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 檢查 MVIEW 狀態
        success = check_mview_status(client)
        
        if success:
            print("\n✅ 狀態檢查完成")
        
        return success
        
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