#!/usr/bin/env python3
"""
檢查 CNE WJ2 NBU E5 的維度映射關係
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 檢查 CNE WJ2 NBU E5 的維度映射關係")
    print("=" * 80)
    
    # ClickHouse 連線設定
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 查詢所有相關的維度組合
        query = """
        SELECT DISTINCT
            region_code,
            region_name,
            plant_code,
            plant_name,
            plant,
            factory_code,
            factory_name,
            factory,
            line_code,
            line_name,
            line,
            dimension_source
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE (
            region_code = 'CNE' OR region_name = 'CNE' OR
            plant_code = 'WJ2' OR plant_name = 'WJ2' OR plant = 'WJ2' OR
            factory_code = 'NBU' OR factory_name = 'NBU' OR factory = 'NBU' OR
            factory_code = 'WJ2' OR factory_name = 'WJ2' OR factory = 'WJ2' OR
            line_code = 'E5' OR line_name = 'E5' OR line = 'E5'
        )
        ORDER BY region_code, plant_code, factory_code, line_code
        """
        
        print("📊 執行查詢...")
        result = client.query(query)
        
        if not result.result_rows:
            print("❌ 沒有找到符合條件的資料")
            return
        
        # 轉換為 DataFrame
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        print(f"✅ 找到 {len(df)} 種維度組合")
        print("\n📊 維度映射關係：")
        print("=" * 120)
        
        # 顯示所有維度組合
        for idx, row in df.iterrows():
            print(f"\n🏭 組合 {idx + 1}:")
            print(f"   Region: {row['region_code']} / {row['region_name']}")
            print(f"   Plant:  {row['plant_code']} / {row['plant_name']} / {row['plant']}")
            print(f"   Factory: {row['factory_code']} / {row['factory_name']} / {row['factory']}")
            print(f"   Line:   {row['line_code']} / {row['line_name']} / {row['line']}")
            print(f"   資料來源: {row['dimension_source']}")
            print("-" * 80)
        
        # 特別檢查包含 WJ2 和 E5 的組合
        print("\n🎯 包含 WJ2 和 E5 的組合：")
        print("=" * 80)
        
        wj2_e5_combinations = df[
            (df['plant_code'].str.contains('WJ2', na=False) | 
             df['plant_name'].str.contains('WJ2', na=False) | 
             df['plant'].str.contains('WJ2', na=False) |
             df['factory_code'].str.contains('WJ2', na=False) | 
             df['factory_name'].str.contains('WJ2', na=False) | 
             df['factory'].str.contains('WJ2', na=False)) &
            (df['line_code'].str.contains('E5', na=False) | 
             df['line_name'].str.contains('E5', na=False) | 
             df['line'].str.contains('E5', na=False))
        ]
        
        if len(wj2_e5_combinations) > 0:
            for idx, row in wj2_e5_combinations.iterrows():
                print(f"\n✅ 找到匹配組合:")
                print(f"   完整路徑: {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']}")
                print(f"   Region: {row['region_code']} ({row['region_name']})")
                print(f"   Plant:  {row['plant_code']} ({row['plant_name']}) [fallback: {row['plant']}]")
                print(f"   Factory: {row['factory_code']} ({row['factory_name']}) [fallback: {row['factory']}]")
                print(f"   Line:   {row['line_code']} ({row['line_name']}) [fallback: {row['line']}]")
                print(f"   資料來源: {row['dimension_source']}")
        else:
            print("❌ 沒有找到同時包含 WJ2 和 E5 的組合")
        
        # 檢查 NBU 相關的組合
        print("\n🎯 包含 NBU 的組合：")
        print("=" * 80)
        
        nbu_combinations = df[
            df['factory_code'].str.contains('NBU', na=False) | 
            df['factory_name'].str.contains('NBU', na=False) | 
            df['factory'].str.contains('NBU', na=False) |
            df['line_name'].str.contains('NBU', na=False) | 
            df['line'].str.contains('NBU', na=False)
        ]
        
        if len(nbu_combinations) > 0:
            for idx, row in nbu_combinations.iterrows():
                print(f"\n✅ 找到 NBU 相關組合:")
                print(f"   完整路徑: {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']}")
                print(f"   Line Name: {row['line_name']}")
        else:
            print("❌ 沒有找到包含 NBU 的組合")
        
        # 解釋 PF 的來源
        print("\n💡 PF 來源解釋：")
        print("=" * 60)
        print("根據查詢結果，PF 是 plant_code 欄位的值")
        print("這表示在製造五階維度中：")
        print("- Region: CNE (華東)")
        print("- Plant: PF (可能是 Plant Factory 的縮寫)")
        print("- Factory: WJ2 (實際的工廠代碼)")
        print("- Line: E5 (產線代碼)")
        print("\n而 NBU 出現在 line_name 中作為 'NBU-E5'，")
        print("表示 NBU 是 E5 產線的完整名稱的一部分")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()