#!/usr/bin/env python3
"""
檢查 CNE WJ2 NBU E5 在 2025-12-25 到 2025-12-31 期間所有可用的日期和 vx_type
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 檢查 CNE WJ2 NBU E5 在 2025-12-25 ~ 2025-12-31 期間的所有資料")
    print("=" * 80)
    
    # ClickHouse 連線設定
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 查詢所有相關資料
        query = """
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
            completion_rate,
            progress_rate
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE snapshot_date >= '2025-12-25'
          AND snapshot_date <= '2025-12-31'
          AND region_code = 'CNE'
          AND plant_code = 'PF'
          AND factory_code = 'WJ2'
          AND line_code = 'E5'
        ORDER BY snapshot_date ASC, vx_type ASC
        """
        
        print("📊 執行查詢...")
        result = client.query(query)
        
        if not result.result_rows:
            print("❌ 沒有找到符合條件的資料")
            
            # 檢查可用的日期範圍
            date_query = """
            SELECT DISTINCT snapshot_date
            FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
            WHERE region_code = 'CNE'
              AND plant_code = 'PF'
              AND factory_code = 'WJ2'
              AND line_code = 'E5'
            ORDER BY snapshot_date DESC
            LIMIT 10
            """
            
            print("\n🔍 檢查可用的日期...")
            date_result = client.query(date_query)
            
            if date_result.result_rows:
                print("\n📅 最近 10 個可用日期：")
                for row in date_result.result_rows:
                    print(f"   {row[0]}")
            
            return
        
        # 轉換為 DataFrame
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        print(f"✅ 找到 {len(df)} 筆資料")
        print("\n📊 CNE-PF-WJ2-E5 每日任務狀態統計：")
        print("=" * 120)
        
        # 按日期分組顯示
        for date in df['snapshot_date'].unique():
            date_data = df[df['snapshot_date'] == date]
            print(f"\n📅 日期: {date}")
            print("-" * 60)
            
            for _, row in date_data.iterrows():
                print(f"   🎯 {row['vx_type']} 類型:")
                print(f"      總任務數: {row['sum_total_task_qty']:,}")
                print(f"      Todo: {row['sum_todo_qty']:,}, Doing: {row['sum_doing_qty']:,}, Done: {row['sum_done_qty']:,}")
                print(f"      完成率: {row['completion_rate']:.1f}%, 執行率: {row['progress_rate']:.1f}%")
        
        # 統計摘要
        print("\n📈 統計摘要：")
        print("=" * 60)
        
        # 按 vx_type 分組統計
        vx_summary = df.groupby('vx_type').agg({
            'sum_total_task_qty': ['count', 'sum', 'mean'],
            'sum_todo_qty': 'sum',
            'sum_doing_qty': 'sum', 
            'sum_done_qty': 'sum',
            'completion_rate': 'mean',
            'progress_rate': 'mean'
        }).round(1)
        
        print("📊 按 VX 類型統計：")
        for vx_type in df['vx_type'].unique():
            vx_data = df[df['vx_type'] == vx_type]
            days = len(vx_data)
            total_tasks = vx_data['sum_total_task_qty'].sum()
            total_todo = vx_data['sum_todo_qty'].sum()
            total_doing = vx_data['sum_doing_qty'].sum()
            total_done = vx_data['sum_done_qty'].sum()
            avg_completion = vx_data['completion_rate'].mean()
            avg_progress = vx_data['progress_rate'].mean()
            
            print(f"\n   🎯 {vx_type} 類型 ({days} 天):")
            print(f"      總任務數: {total_tasks:,}")
            print(f"      Todo: {total_todo:,}, Doing: {total_doing:,}, Done: {total_done:,}")
            print(f"      平均完成率: {avg_completion:.1f}%")
            print(f"      平均執行率: {avg_progress:.1f}%")
        
        # 儲存詳細資料
        output_file = f"logs/cne_wj2_nbu_e5_all_data_20251225_20251231.csv"
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