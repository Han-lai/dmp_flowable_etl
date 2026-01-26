#!/usr/bin/env python3
"""
執行維度補齊邏輯驗證
規則：VARINST 有資料就用 VARINST，VARINST 沒資料才用 MDM 補齊
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 執行維度補齊邏輯驗證")
    print("規則：VARINST 優先，MDM 補齊缺失")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 讀取並執行驗證 SQL
        with open('sql/validate_dimension_backfill_logic.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print("📊 執行維度補齊邏輯驗證...")
        result = client.query(sql_content)
        
        if result.result_rows:
            print("✅ 驗收表產出成功")
            print("=" * 100)
            
            # 建立 DataFrame
            df = pd.DataFrame(result.result_rows, columns=result.column_names)
            
            # 顯示驗收表
            print(f"{'PROC_INST_ID':<40} {'DIMENSION':<10} {'VARINST':<10} {'MDM':<10} {'FINAL':<10} {'SOURCE':<10}")
            print("-" * 100)
            
            for _, row in df.iterrows():
                proc_id_short = row['proc_inst_id'][-12:]  # 只顯示最後12位
                print(f"{proc_id_short:<40} {row['dimension']:<10} {row['varinst_value']:<10} {row['mdm_value']:<10} {row['final_value']:<10} {row['source']:<10}")
            
            print("\n" + "=" * 100)
            
            # 驗證邏輯正確性
            print("🔍 驗證邏輯正確性:")
            
            # 檢查 1: VARINST 有值的情況，不應被 MDM 覆蓋
            varinst_has_value = df[(df['varinst_value'] != 'NULL')]
            varinst_overridden = varinst_has_value[varinst_has_value['source'] != 'VARINST']
            
            if len(varinst_overridden) == 0:
                print("✅ 檢查 1 通過: 有值的 VARINST 沒被 MDM 覆蓋")
            else:
                print("❌ 檢查 1 失敗: 發現 VARINST 有值但被 MDM 覆蓋的情況:")
                for _, row in varinst_overridden.iterrows():
                    print(f"   {row['proc_inst_id'][-12:]} {row['dimension']}: VARINST={row['varinst_value']} 但 SOURCE={row['source']}")
            
            # 檢查 2: VARINST 缺值的情況，應該用 MDM 補齊
            varinst_missing = df[(df['varinst_value'] == 'NULL')]
            mdm_backfilled = varinst_missing[varinst_missing['source'] == 'MDM']
            
            print(f"✅ 檢查 2: VARINST 缺值 {len(varinst_missing)} 筆，MDM 補齊 {len(mdm_backfilled)} 筆")
            
            if len(varinst_missing) > 0:
                backfill_rate = len(mdm_backfilled) / len(varinst_missing) * 100
                print(f"   MDM 補齊成功率: {backfill_rate:.1f}%")
            
            # 檢查 3: 資料來源標記正確性
            source_correct = True
            for _, row in df.iterrows():
                if row['varinst_value'] != 'NULL' and row['source'] != 'VARINST':
                    source_correct = False
                    break
                if row['varinst_value'] == 'NULL' and row['mdm_value'] != 'NULL' and row['source'] != 'MDM':
                    source_correct = False
                    break
            
            if source_correct:
                print("✅ 檢查 3 通過: 資料來源標記正確")
            else:
                print("❌ 檢查 3 失敗: 資料來源標記不正確")
            
            # 統計摘要
            print(f"\n📊 統計摘要:")
            print(f"   總記錄數: {len(df)}")
            print(f"   VARINST 來源: {len(df[df['source'] == 'VARINST'])}")
            print(f"   MDM 來源: {len(df[df['source'] == 'MDM'])}")
            print(f"   缺失: {len(df[df['source'] == 'MISSING'])}")
            
            # 按維度統計
            print(f"\n📊 按維度統計:")
            for dim in ['region', 'plant', 'factory', 'lineName']:
                dim_data = df[df['dimension'] == dim]
                varinst_count = len(dim_data[dim_data['source'] == 'VARINST'])
                mdm_count = len(dim_data[dim_data['source'] == 'MDM'])
                missing_count = len(dim_data[dim_data['source'] == 'MISSING'])
                print(f"   {dim:<10}: VARINST={varinst_count}, MDM={mdm_count}, MISSING={missing_count}")
            
            return df
            
        else:
            print("❌ 無驗證結果")
            return None
            
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        client.close()

if __name__ == "__main__":
    result = main()
    if result is not None:
        print(f"\n✅ 維度補齊邏輯驗證完成")
        
        # 儲存驗收表到 CSV
        result.to_csv('validation_results/dimension_backfill_acceptance_table.csv', index=False, encoding='utf-8')
        print(f"📁 驗收表已儲存: validation_results/dimension_backfill_acceptance_table.csv")
    else:
        print("\n❌ 驗證失敗")