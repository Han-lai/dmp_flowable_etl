#!/usr/bin/env python3
"""
檢查 Gold 表中實際的 CNE 相關資料
找出目前系統中使用的維度組合
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 檢查 Gold 表中實際的 CNE 相關資料")
    print("=" * 80)
    
    # ClickHouse 連線設定
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 檢查 Gold 表中所有 CNE 相關的維度組合
        print("📊 步驟 1：檢查 Gold 表中所有 CNE 相關的維度組合")
        cne_query = """
        SELECT DISTINCT
            region_code,
            region_name,
            plant_code,
            plant_name,
            factory_code,
            factory_name,
            line_code,
            line_name,
            vx_type,
            count() as record_count
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE region_code = 'CNE' OR region_name = 'CNE'
        GROUP BY region_code, region_name, plant_code, plant_name, factory_code, factory_name, line_code, line_name, vx_type
        ORDER BY record_count DESC
        LIMIT 50
        """
        
        result = client.query(cne_query)
        
        if result.result_rows:
            print("✅ 找到 CNE 相關的維度組合：")
            df = pd.DataFrame(result.result_rows, columns=result.column_names)
            for _, row in df.iterrows():
                print(f"   🏭 {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']} ({row['vx_type']}) - 記錄數: {row['record_count']}")
        else:
            print("❌ 沒有找到 CNE 相關資料")
        
        # 2. 檢查包含 WJ2 的維度組合
        print("\n📊 步驟 2：檢查包含 WJ2 的維度組合")
        wj2_query = """
        SELECT DISTINCT
            region_code,
            plant_code,
            factory_code,
            line_code,
            vx_type,
            count() as record_count
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE plant_code = 'WJ2' OR plant_name = 'WJ2' OR plant = 'WJ2'
        GROUP BY region_code, plant_code, factory_code, line_code, vx_type
        ORDER BY record_count DESC
        LIMIT 20
        """
        
        wj2_result = client.query(wj2_query)
        
        if wj2_result.result_rows:
            print("✅ 找到 WJ2 相關的維度組合：")
            df_wj2 = pd.DataFrame(wj2_result.result_rows, columns=wj2_result.column_names)
            for _, row in df_wj2.iterrows():
                print(f"   🏭 {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']} ({row['vx_type']}) - 記錄數: {row['record_count']}")
        else:
            print("❌ 沒有找到 WJ2 相關資料")
        
        # 3. 檢查包含 NBU 的維度組合
        print("\n📊 步驟 3：檢查包含 NBU 的維度組合")
        nbu_query = """
        SELECT DISTINCT
            region_code,
            plant_code,
            factory_code,
            line_code,
            vx_type,
            count() as record_count
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE factory_code = 'NBU' OR factory_name = 'NBU' OR factory = 'NBU'
        GROUP BY region_code, plant_code, factory_code, line_code, vx_type
        ORDER BY record_count DESC
        LIMIT 20
        """
        
        nbu_result = client.query(nbu_query)
        
        if nbu_result.result_rows:
            print("✅ 找到 NBU 相關的維度組合：")
            df_nbu = pd.DataFrame(nbu_result.result_rows, columns=nbu_result.column_names)
            for _, row in df_nbu.iterrows():
                print(f"   🏭 {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']} ({row['vx_type']}) - 記錄數: {row['record_count']}")
        else:
            print("❌ 沒有找到 NBU 相關資料")
        
        # 4. 檢查包含 E5 的維度組合
        print("\n📊 步驟 4：檢查包含 E5 的維度組合")
        e5_query = """
        SELECT DISTINCT
            region_code,
            plant_code,
            factory_code,
            line_code,
            line_name,
            vx_type,
            count() as record_count
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE line_code = 'E5' OR line_name = 'E5' OR line = 'E5' OR line_name LIKE '%E5%'
        GROUP BY region_code, plant_code, factory_code, line_code, line_name, vx_type
        ORDER BY record_count DESC
        LIMIT 20
        """
        
        e5_result = client.query(e5_query)
        
        if e5_result.result_rows:
            print("✅ 找到 E5 相關的維度組合：")
            df_e5 = pd.DataFrame(e5_result.result_rows, columns=e5_result.column_names)
            for _, row in df_e5.iterrows():
                print(f"   🏭 {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']} ({row['line_name']}) ({row['vx_type']}) - 記錄數: {row['record_count']}")
        else:
            print("❌ 沒有找到 E5 相關資料")
        
        # 5. 檢查之前查詢到的 CNE-PF-WJ2-E5 組合
        print("\n📊 步驟 5：檢查 CNE-PF-WJ2-E5 組合的詳細資料")
        specific_query = """
        SELECT 
            snapshot_date,
            region_code,
            plant_code,
            factory_code,
            line_code,
            vx_type,
            sum_total_task_qty,
            sum_todo_qty,
            sum_doing_qty,
            sum_done_qty,
            completion_rate
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE region_code = 'CNE'
          AND plant_code = 'PF'
          AND factory_code = 'WJ2'
          AND line_code = 'E5'
          AND vx_type = 'V3'
          AND snapshot_date >= '2025-12-25'
          AND snapshot_date <= '2025-12-31'
        ORDER BY snapshot_date
        """
        
        specific_result = client.query(specific_query)
        
        if specific_result.result_rows:
            print("✅ 找到 CNE-PF-WJ2-E5 V3 的任務資料：")
            df_specific = pd.DataFrame(specific_result.result_rows, columns=specific_result.column_names)
            for _, row in df_specific.iterrows():
                print(f"   📅 {row['snapshot_date']}: Total={row['sum_total_task_qty']}, Todo={row['sum_todo_qty']}, Doing={row['sum_doing_qty']}, Done={row['sum_done_qty']}, Rate={row['completion_rate']:.1f}%")
        else:
            print("❌ 沒有找到 CNE-PF-WJ2-E5 V3 的任務資料")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()