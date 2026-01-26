#!/usr/bin/env python3
"""
查詢 CNE WJ2 NBU E5 V3 在 2025-12-25 到 2025-12-31 期間每天的任務狀態數據
"""

import clickhouse_connect
import pandas as pd
from datetime import datetime, timedelta

def main():
    print("🔍 查詢 CNE WJ2 NBU E5 V3 每日任務狀態數據 (2025-12-25 ~ 2025-12-31)")
    print("=" * 80)
    
    # ClickHouse 連線設定
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 查詢 Gold 層表格 - 根據實際資料結構調整
        query = """
        SELECT 
            snapshot_date,
            region_code,
            region_name,
            plant_code,
            plant_name,
            factory_code,
            factory_name,
            line_code,
            line_name,
            vx_type,
            sum_total_task_qty,
            sum_todo_qty,
            sum_doing_qty,
            sum_done_qty,
            completion_rate,
            progress_rate,
            dimension_source
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE snapshot_date >= '2025-12-25'
          AND snapshot_date <= '2025-12-31'
          AND region_code = 'CNE'
          AND plant_code = 'PF'
          AND factory_code = 'WJ2'
          AND line_code = 'E5'
          AND vx_type = 'V3'
        ORDER BY snapshot_date ASC
        """
        
        print("📊 執行查詢...")
        result = client.query(query)
        
        if not result.result_rows:
            print("❌ 沒有找到符合條件的資料")
            
            # 檢查是否有相關資料
            check_query = """
            SELECT DISTINCT 
                region_code, region_name,
                plant_code, plant_name, plant,
                factory_code, factory_name, factory,
                line_code, line_name, line,
                vx_type
            FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
            WHERE snapshot_date >= '2025-12-25'
              AND snapshot_date <= '2025-12-31'
              AND (
                  (region_code = 'CNE' OR region_name = 'CNE') OR
                  (plant_code = 'WJ2' OR plant_name = 'WJ2' OR plant = 'WJ2') OR
                  (factory_code = 'NBU' OR factory_name = 'NBU' OR factory = 'NBU') OR
                  (line_code = 'E5' OR line_name = 'E5' OR line = 'E5') OR
                  vx_type = 'V3'
              )
            LIMIT 20
            """
            
            print("\n🔍 檢查相關資料...")
            check_result = client.query(check_query)
            
            if check_result.result_rows:
                print("\n📋 找到相關的維度組合：")
                df_check = pd.DataFrame(check_result.result_rows, columns=check_result.column_names)
                print(df_check.to_string(index=False))
            else:
                print("❌ 在指定時間範圍內沒有找到任何相關資料")
            
            return
        
        # 轉換為 DataFrame
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        print(f"✅ 找到 {len(df)} 筆資料")
        print("\n📊 CNE WJ2 NBU E5 V3 每日任務狀態統計：")
        print("=" * 120)
        
        # 格式化顯示
        for _, row in df.iterrows():
            print(f"📅 日期: {row['snapshot_date']}")
            print(f"   🏭 維度: {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']} ({row['vx_type']})")
            print(f"   📊 任務狀態:")
            print(f"      總任務數: {row['sum_total_task_qty']:,}")
            print(f"      Todo 任務: {row['sum_todo_qty']:,}")
            print(f"      Doing 任務: {row['sum_doing_qty']:,}")
            print(f"      Done 任務: {row['sum_done_qty']:,}")
            print(f"   📈 完成率: {row['completion_rate']:.1f}%")
            print(f"   📈 執行率: {row['progress_rate']:.1f}%")
            print(f"   🔗 資料來源: {row['dimension_source']}")
            print("-" * 80)
        
        # 統計摘要
        print("\n📈 統計摘要：")
        print("=" * 60)
        total_days = len(df)
        avg_total = df['sum_total_task_qty'].mean()
        avg_todo = df['sum_todo_qty'].mean()
        avg_doing = df['sum_doing_qty'].mean()
        avg_done = df['sum_done_qty'].mean()
        avg_completion = df['completion_rate'].mean()
        avg_progress = df['progress_rate'].mean()
        
        print(f"📊 統計期間: {total_days} 天")
        print(f"📊 平均任務數:")
        print(f"   總任務數: {avg_total:.1f}")
        print(f"   Todo 任務: {avg_todo:.1f}")
        print(f"   Doing 任務: {avg_doing:.1f}")
        print(f"   Done 任務: {avg_done:.1f}")
        print(f"📊 平均完成率: {avg_completion:.1f}%")
        print(f"📊 平均執行率: {avg_progress:.1f}%")
        
        # 趨勢分析
        if len(df) > 1:
            print("\n📈 趨勢分析：")
            first_day = df.iloc[0]
            last_day = df.iloc[-1]
            
            total_change = last_day['sum_total_task_qty'] - first_day['sum_total_task_qty']
            completion_change = last_day['completion_rate'] - first_day['completion_rate']
            
            print(f"📊 總任務數變化: {total_change:+.0f}")
            print(f"📊 完成率變化: {completion_change:+.1f}%")
        
        # 儲存詳細資料到 CSV
        output_file = f"logs/cne_wj2_nbu_e5_v3_daily_tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 詳細資料已儲存至: {output_file}")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()