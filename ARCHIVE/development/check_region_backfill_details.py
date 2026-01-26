#!/usr/bin/env python3
"""
檢查被補齊 region 的完整 VARINST 資料
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 檢查被補齊 region 的完整 VARINST 資料")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    target_proc_inst_ids = [
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7',
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]
    
    try:
        # 執行完整的 VARINST 查詢
        query = f"""
        SELECT 
            ID_, REV_, PROC_INST_ID_, EXECUTION_ID_, TASK_ID_, 
            NAME_, VAR_TYPE_, SCOPE_ID_, SUB_SCOPE_ID_, SCOPE_TYPE_, 
            BYTEARRAY_ID_, DOUBLE_, LONG_, TEXT_, TEXT2_, 
            CREATE_TIME_, LAST_UPDATED_TIME_, META_INFO_, _sync_time
        FROM bronze.bpm_act_hi_varinst
        WHERE PROC_INST_ID_ IN ({','.join([f"'{pid}'" for pid in target_proc_inst_ids])})
        ORDER BY PROC_INST_ID_, NAME_, CREATE_TIME_
        """
        
        print("📊 執行 VARINST 完整資料查詢...")
        result = client.query(query)
        
        if result.result_rows:
            print(f"✅ 查詢成功，共 {len(result.result_rows)} 筆記錄")
            
            # 建立 DataFrame
            df = pd.DataFrame(result.result_rows, columns=result.column_names)
            
            # 按 PROC_INST_ID_ 分組顯示
            for proc_id in target_proc_inst_ids:
                proc_data = df[df['PROC_INST_ID_'] == proc_id]
                print(f"\n🔍 PROC_INST_ID: {proc_id}")
                print(f"   記錄數: {len(proc_data)}")
                
                if len(proc_data) > 0:
                    # 顯示維度相關的記錄
                    dimension_data = proc_data[proc_data['NAME_'].isin(['region', 'plant', 'factory', 'lineName'])]
                    
                    if len(dimension_data) > 0:
                        print("   📋 維度相關記錄:")
                        for _, row in dimension_data.iterrows():
                            print(f"      {row['NAME_']}: {row['TEXT_']} (ID: {row['ID_']}, 建立時間: {row['CREATE_TIME_']})")
                    
                    # 檢查是否有 region 記錄
                    region_data = proc_data[proc_data['NAME_'] == 'region']
                    if len(region_data) == 0:
                        print("   ❌ 確認無 region 記錄 - 需要 MDM 補齊")
                    else:
                        print(f"   ✅ 有 region 記錄: {region_data.iloc[0]['TEXT_']}")
                    
                    # 顯示其他重要欄位
                    important_fields = proc_data[proc_data['NAME_'].isin([
                        'moNumber', 'scheduleNumber', 'productionArea', 'modelName', 'orderType'
                    ])]
                    
                    if len(important_fields) > 0:
                        print("   📋 其他重要欄位:")
                        for _, row in important_fields.iterrows():
                            print(f"      {row['NAME_']}: {row['TEXT_']}")
                else:
                    print("   ❌ 無任何 VARINST 記錄")
            
            # 統計分析
            print(f"\n📊 統計分析:")
            print(f"   總記錄數: {len(df)}")
            
            # 按 NAME_ 統計
            name_counts = df['NAME_'].value_counts()
            print(f"   按變數名稱統計:")
            for name, count in name_counts.head(10).items():
                print(f"      {name}: {count} 筆")
            
            # 檢查維度完整性
            print(f"\n📊 維度完整性檢查:")
            for proc_id in target_proc_inst_ids:
                proc_data = df[df['PROC_INST_ID_'] == proc_id]
                
                region_count = len(proc_data[proc_data['NAME_'] == 'region'])
                plant_count = len(proc_data[proc_data['NAME_'] == 'plant'])
                factory_count = len(proc_data[proc_data['NAME_'] == 'factory'])
                line_count = len(proc_data[proc_data['NAME_'] == 'lineName'])
                
                print(f"   {proc_id[-12:]}:")
                print(f"      region: {region_count}, plant: {plant_count}, factory: {factory_count}, lineName: {line_count}")
            
            # 顯示 MDM 補齊的 region 值
            print(f"\n📊 MDM 補齊的 region 值:")
            
            # 取得 lineName 並查詢對應的 MDM region
            mdm_query = """
            WITH target_lines AS (
                SELECT DISTINCT 
                    v.PROC_INST_ID_,
                    v.TEXT_ AS line_name
                FROM bronze.bpm_act_hi_varinst v
                WHERE v.PROC_INST_ID_ IN ('3c40f619-c593-11f0-8d58-1e564a6128f7',
                                         '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7',
                                         '3ca530c5-d938-11f0-8eb2-761d901080ab',
                                         '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
                                         '3c60482b-ecf9-11f0-ba59-92564f99f227',
                                         '3ca93700-ef50-11f0-a787-0a5a5063cfa7')
                  AND v.NAME_ = 'lineName'
                  AND v.TEXT_ IS NOT NULL
                  AND v.TEXT_ != ''
            )
            
            SELECT 
                t.PROC_INST_ID_,
                t.line_name,
                mdm.region_code AS mdm_region,
                mdm.plant_code AS mdm_plant,
                mdm.factory_code AS mdm_factory
            FROM target_lines t
            LEFT JOIN silver.dim_mfg_five_level mdm ON t.line_name = mdm.line_name
            ORDER BY t.PROC_INST_ID_
            """
            
            mdm_result = client.query(mdm_query)
            if mdm_result.result_rows:
                mdm_df = pd.DataFrame(mdm_result.result_rows, columns=mdm_result.column_names)
                
                for _, row in mdm_df.iterrows():
                    print(f"   {row['PROC_INST_ID_'][-12:]}:")
                    print(f"      lineName: {row['line_name']} → MDM region: {row['mdm_region']}")
                    print(f"      MDM 完整維度: {row['mdm_region']}-{row['mdm_plant']}-{row['mdm_factory']}-{row['line_name']}")
            
            return df
            
        else:
            print("❌ 無查詢結果")
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
        print(f"\n✅ 查詢完成")
    else:
        print("\n❌ 查詢失敗")