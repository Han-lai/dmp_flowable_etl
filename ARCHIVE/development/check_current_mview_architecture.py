#!/usr/bin/env python3
"""
檢查目前金銀銅 mview 架構
確認哪些表需要更新以應用維度補齊邏輯
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 檢查目前金銀銅 mview 架構")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 檢查所有 mview 和相關表
        print("📊 步驟 1: 檢查所有 mview 和相關表")
        print("-" * 50)
        
        tables_query = """
        SELECT 
            database,
            name,
            engine,
            CASE 
                WHEN name LIKE '%bronze%' OR database = 'bronze' THEN 'Bronze'
                WHEN name LIKE '%silver%' OR database = 'silver' THEN 'Silver'
                WHEN name LIKE '%gold%' OR database = 'gold' THEN 'Gold'
                ELSE 'Other'
            END AS layer,
            total_rows,
            total_bytes
        FROM system.tables
        WHERE (database IN ('bronze', 'silver', 'gold') 
               OR name LIKE '%mview%' 
               OR name LIKE '%mv_%'
               OR name LIKE '%fact_%'
               OR name LIKE '%dim_%')
          AND engine IN ('MaterializedView', 'MergeTree', 'ReplacingMergeTree')
        ORDER BY layer, database, name
        """
        
        tables_result = client.query(tables_query)
        if tables_result.result_rows:
            tables_df = pd.DataFrame(tables_result.result_rows, columns=tables_result.column_names)
            
            print("✅ 找到相關表格:")
            current_layer = None
            for _, row in tables_df.iterrows():
                if row['layer'] != current_layer:
                    current_layer = row['layer']
                    print(f"\n🏷️ {current_layer} Layer:")
                
                size_mb = row['total_bytes'] / (1024 * 1024) if row['total_bytes'] else 0
                print(f"   {row['database']}.{row['name']} ({row['engine']}) - {row['total_rows']:,} rows, {size_mb:.1f}MB")
        
        print()
        
        # 2. 檢查包含五階維度的關鍵表
        print("📊 步驟 2: 檢查包含五階維度的關鍵表")
        print("-" * 50)
        
        dimension_tables = [
            'silver.mv_fact_task_vx_attribution_mdm',
            'silver.dim_mfg_five_level',
            'gold.mv_l5_task_completion_summary',
            'gold.l5_dashboard_summary'
        ]
        
        for table in dimension_tables:
            try:
                # 檢查表是否存在
                exists_query = f"SELECT COUNT(*) as row_count FROM {table} LIMIT 1"
                exists_result = client.query(exists_query)
                
                if exists_result.result_rows:
                    row_count = exists_result.result_rows[0][0]
                    print(f"✅ {table}: {row_count:,} rows")
                    
                    # 檢查維度欄位
                    desc_query = f"DESCRIBE {table}"
                    desc_result = client.query(desc_query)
                    
                    if desc_result.result_rows:
                        desc_df = pd.DataFrame(desc_result.result_rows, columns=desc_result.column_names)
                        dimension_cols = desc_df[desc_df['name'].isin(['region', 'plant', 'factory', 'lineName', 'line_name', 'region_code', 'plant_code', 'factory_code'])]
                        
                        if len(dimension_cols) > 0:
                            print(f"   📋 維度欄位:")
                            for _, col in dimension_cols.iterrows():
                                print(f"      {col['name']}: {col['type']}")
                        else:
                            print(f"   ❌ 未找到標準維度欄位")
                else:
                    print(f"❌ {table}: 表不存在或無資料")
                    
            except Exception as e:
                print(f"❌ {table}: 檢查失敗 - {str(e)}")
        
        print()
        
        # 3. 檢查現有維度補齊邏輯
        print("📊 步驟 3: 檢查現有維度補齊邏輯")
        print("-" * 50)
        
        # 檢查 silver.mv_fact_task_vx_attribution_mdm 的邏輯
        try:
            sample_query = """
            SELECT 
                region, plant, factory, line_name,
                region_source, plant_source, factory_source, line_source,
                COUNT(*) as record_count
            FROM silver.mv_fact_task_vx_attribution_mdm
            WHERE snapshot_date >= '2025-12-01'
            GROUP BY region, plant, factory, line_name, region_source, plant_source, factory_source, line_source
            ORDER BY record_count DESC
            LIMIT 10
            """
            
            sample_result = client.query(sample_query)
            if sample_result.result_rows:
                sample_df = pd.DataFrame(sample_result.result_rows, columns=sample_result.column_names)
                
                print("✅ silver.mv_fact_task_vx_attribution_mdm 維度補齊狀況:")
                for _, row in sample_df.iterrows():
                    print(f"   {row['region']}-{row['plant']}-{row['factory']}-{row['line_name']}")
                    print(f"      來源: region={row['region_source']}, plant={row['plant_source']}, factory={row['factory_source']}, line={row['line_source']}")
                    print(f"      記錄數: {row['record_count']:,}")
                    print()
            else:
                print("❌ silver.mv_fact_task_vx_attribution_mdm 無資料")
                
        except Exception as e:
            print(f"❌ 檢查維度補齊邏輯失敗: {str(e)}")
        
        print()
        
        # 4. 檢查需要更新的表
        print("📊 步驟 4: 檢查需要更新的表")
        print("-" * 50)
        
        update_candidates = []
        
        # 檢查各層級的表是否已實作維度補齊
        tables_to_check = [
            ('silver.mv_fact_task_vx_attribution_mdm', 'Silver層核心事實表'),
            ('gold.mv_l5_task_completion_summary', 'Gold層任務完成摘要'),
            ('gold.l5_dashboard_summary', 'Gold層儀表板摘要')
        ]
        
        for table_name, description in tables_to_check:
            try:
                # 檢查是否有資料來源欄位
                desc_query = f"DESCRIBE {table_name}"
                desc_result = client.query(desc_query)
                
                if desc_result.result_rows:
                    desc_df = pd.DataFrame(desc_result.result_rows, columns=desc_result.column_names)
                    source_cols = desc_df[desc_df['name'].str.contains('_source', case=False)]
                    
                    if len(source_cols) > 0:
                        print(f"✅ {table_name} ({description})")
                        print(f"   已有資料來源追蹤欄位: {', '.join(source_cols['name'].tolist())}")
                        
                        # 檢查是否有 MDM 補齊記錄
                        mdm_check_query = f"""
                        SELECT 
                            COUNT(*) as total_records,
                            SUM(CASE WHEN region_source = 'MDM' THEN 1 ELSE 0 END) as mdm_region_count,
                            SUM(CASE WHEN plant_source = 'MDM' THEN 1 ELSE 0 END) as mdm_plant_count,
                            SUM(CASE WHEN factory_source = 'MDM' THEN 1 ELSE 0 END) as mdm_factory_count,
                            SUM(CASE WHEN line_source = 'MDM' THEN 1 ELSE 0 END) as mdm_line_count
                        FROM {table_name}
                        WHERE snapshot_date >= '2025-12-01'
                        """
                        
                        mdm_result = client.query(mdm_check_query)
                        if mdm_result.result_rows:
                            mdm_data = mdm_result.result_rows[0]
                            total = mdm_data[0]
                            mdm_region = mdm_data[1]
                            
                            if total > 0:
                                mdm_region_pct = (mdm_region / total) * 100
                                print(f"   MDM 補齊比例: region={mdm_region_pct:.1f}% ({mdm_region:,}/{total:,})")
                                
                                if mdm_region_pct > 0:
                                    print(f"   ✅ 已實作維度補齊邏輯")
                                else:
                                    print(f"   ⚠️ 有補齊邏輯但無 MDM 補齊記錄")
                                    update_candidates.append((table_name, description, "需要檢查補齊邏輯"))
                            else:
                                print(f"   ❌ 無資料")
                                update_candidates.append((table_name, description, "無資料"))
                    else:
                        print(f"❌ {table_name} ({description})")
                        print(f"   缺少資料來源追蹤欄位")
                        update_candidates.append((table_name, description, "需要新增維度補齊邏輯"))
                else:
                    print(f"❌ {table_name} ({description})")
                    print(f"   表不存在")
                    update_candidates.append((table_name, description, "表不存在"))
                    
            except Exception as e:
                print(f"❌ {table_name} ({description})")
                print(f"   檢查失敗: {str(e)}")
                update_candidates.append((table_name, description, f"檢查失敗: {str(e)}"))
        
        print()
        
        # 5. 總結需要更新的表
        print("📊 步驟 5: 總結需要更新的表")
        print("-" * 50)
        
        if update_candidates:
            print("⚠️ 需要更新的表:")
            for table_name, description, reason in update_candidates:
                print(f"   {table_name}")
                print(f"      描述: {description}")
                print(f"      原因: {reason}")
                print()
        else:
            print("✅ 所有表都已正確實作維度補齊邏輯")
        
        # 6. 建議更新順序
        print("📊 步驟 6: 建議更新順序")
        print("-" * 50)
        
        print("🔄 建議更新順序:")
        print("   1. Silver Layer: silver.mv_fact_task_vx_attribution_mdm")
        print("      - 核心事實表，其他表依賴此表")
        print("      - 實作 VARINST 優先，MDM 補齊邏輯")
        print()
        print("   2. Gold Layer: gold.mv_l5_task_completion_summary")
        print("      - L5 任務完成摘要表")
        print("      - 依賴 silver 層資料")
        print()
        print("   3. Gold Layer: gold.l5_dashboard_summary")
        print("      - 儀表板摘要表")
        print("      - 最終使用者介面")
        print()
        print("   4. 其他相關表")
        print("      - 根據依賴關係逐步更新")
        
        return update_candidates
        
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
    
    finally:
        client.close()

if __name__ == "__main__":
    candidates = main()
    if candidates:
        print(f"\n📋 總共需要更新 {len(candidates)} 個表")
    else:
        print(f"\n✅ 架構檢查完成")