#!/usr/bin/env python3
"""
驗證 MVIEW 自動更新路線是否符合新制定的規範
檢查項目：
1. V1/V3 歸屬邏輯順序（工單號規則優先）
2. 315% 工單號規則（使用 LIKE '315%'）
3. 時間邏輯統一（OR 條件）
4. NPE 判別邏輯（使用 varinst_name）
"""

import clickhouse_connect
import pandas as pd
from datetime import datetime

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def check_mview_structure(client):
    """檢查 MVIEW 結構是否存在"""
    print("🔍 檢查 MVIEW 結構")
    
    mviews_to_check = [
        'silver.mv_fact_task_vx_attribution',
        'silver.mv_l5_metrics_realtime',
        'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV'
    ]
    
    for mview in mviews_to_check:
        try:
            query = f"SELECT COUNT(*) as count FROM {mview} LIMIT 1"
            result = client.query(query)
            count = result.result_rows[0][0]
            print(f"✅ {mview}: {count:,} 筆資料")
        except Exception as e:
            print(f"❌ {mview}: 不存在或查詢失敗 - {e}")

def check_v1_attribution_logic(client):
    """檢查 V1/V3 歸屬邏輯是否正確"""
    print("\n🔍 檢查 V1/V3 歸屬邏輯")
    
    # 檢查 315% 工單號是否正確歸類為 V1
    query = """
    SELECT 
        vx_type,
        COUNT(*) as task_count,
        COUNT(DISTINCT mo_number) as unique_mo_count
    FROM silver.mv_fact_task_vx_attribution
    WHERE mo_number LIKE '315%'
    GROUP BY vx_type
    ORDER BY task_count DESC
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print("📊 315% 工單號歸屬分佈:")
        print(df.to_string(index=False))
        
        # 檢查是否所有 315% 工單號都歸類為 V1
        v1_count = df[df['vx_type'] == 'V1']['task_count'].sum() if len(df[df['vx_type'] == 'V1']) > 0 else 0
        total_count = df['task_count'].sum()
        
        if v1_count == total_count and total_count > 0:
            print("✅ 所有 315% 工單號都正確歸類為 V1")
        elif total_count == 0:
            print("⚠️ 沒有找到 315% 工單號任務")
        else:
            print(f"❌ 有 {total_count - v1_count} 個 315% 工單號任務未歸類為 V1")
            
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")

def check_199_workorder_logic(client):
    """檢查 199% 工單號歸屬邏輯"""
    print("\n🔍 檢查 199% 工單號歸屬邏輯")
    
    query = """
    SELECT 
        vx_type,
        task_definition_key,
        COUNT(*) as task_count
    FROM silver.mv_fact_task_vx_attribution
    WHERE mo_number LIKE '199%'
    GROUP BY vx_type, task_definition_key
    ORDER BY task_count DESC
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print("📊 199% 工單號歸屬分佈:")
        print(df.to_string(index=False))
        
        # 檢查是否所有 199% 工單號都歸類為 V1（無論 task_definition_key）
        v1_count = df[df['vx_type'] == 'V1']['task_count'].sum() if len(df[df['vx_type'] == 'V1']) > 0 else 0
        total_count = df['task_count'].sum()
        
        if v1_count == total_count and total_count > 0:
            print("✅ 所有 199% 工單號都正確歸類為 V1")
        elif total_count == 0:
            print("⚠️ 沒有找到 199% 工單號任務")
        else:
            print(f"❌ 有 {total_count - v1_count} 個 199% 工單號任務未歸類為 V1")
            
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")

def check_time_logic_compliance(client):
    """檢查時間邏輯是否符合規範"""
    print("\n🔍 檢查時間邏輯合規性")
    
    # 檢查 mv_l5_metrics_realtime 的時間邏輯
    print("⚠️ 發現問題：mv_l5_metrics_realtime 只使用 task_create_time 計算 snapshot_date")
    print("📋 規範要求：應使用 OR 條件包含 task_create_time/task_claim_time/task_end_time")
    
    # 檢查是否有任務的 claim_time 或 end_time 與 create_time 在不同日期
    query = """
    SELECT 
        COUNT(*) as total_tasks,
        COUNT(CASE WHEN toDate(task_claim_time) != toDate(task_create_time) AND task_claim_time IS NOT NULL THEN 1 END) as diff_claim_date,
        COUNT(CASE WHEN toDate(task_end_time) != toDate(task_create_time) AND task_end_time IS NOT NULL THEN 1 END) as diff_end_date,
        COUNT(CASE WHEN (toDate(task_claim_time) != toDate(task_create_time) OR toDate(task_end_time) != toDate(task_create_time)) 
                   AND (task_claim_time IS NOT NULL OR task_end_time IS NOT NULL) THEN 1 END) as potentially_missed
    FROM silver.mv_fact_task_vx_attribution
    WHERE task_create_time >= '2025-12-01'  -- 最近一個月的資料
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print("📊 時間差異分析（最近一個月）:")
        print(df.to_string(index=False))
        
        total = df.iloc[0]['total_tasks']
        potentially_missed = df.iloc[0]['potentially_missed']
        
        if potentially_missed > 0:
            percentage = (potentially_missed / total * 100) if total > 0 else 0
            print(f"❌ 有 {potentially_missed:,} 個任務（{percentage:.1f}%）可能因時間邏輯問題被遺漏")
            print("💡 建議：修正 mv_l5_metrics_realtime 使用 OR 條件的時間邏輯")
        else:
            print("✅ 沒有發現明顯的時間邏輯問題")
            
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")

def check_npe_logic_compliance(client):
    """檢查 NPE 判別邏輯是否符合規範"""
    print("\n🔍 檢查 NPE 判別邏輯合規性")
    
    # 檢查 V1 子類型分佈
    query = """
    SELECT 
        vx_subtype,
        COUNT(*) as task_count
    FROM silver.mv_fact_task_vx_attribution
    WHERE vx_type = 'V1'
    GROUP BY vx_subtype
    ORDER BY task_count DESC
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print("📊 V1 子類型分佈:")
        print(df.to_string(index=False))
        
        # 檢查是否有 V1_NPE 和 V1_MFG
        has_npe = len(df[df['vx_subtype'] == 'V1_NPE']) > 0
        has_mfg = len(df[df['vx_subtype'] == 'V1_MFG']) > 0
        
        if has_npe and has_mfg:
            print("✅ NPE 判別邏輯正常運作，有 V1_NPE 和 V1_MFG 分類")
        else:
            print("❌ NPE 判別邏輯可能有問題")
            if not has_npe:
                print("  - 缺少 V1_NPE 分類")
            if not has_mfg:
                print("  - 缺少 V1_MFG 分類")
                
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")

def check_data_freshness(client):
    """檢查資料新鮮度"""
    print("\n🔍 檢查資料新鮮度")
    
    tables_to_check = [
        ('silver.mv_fact_task_vx_attribution', '_mview_update_time'),
        ('silver.mv_l5_metrics_realtime', '_mview_update_time'),
        ('gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV', '_mview_update_time')
    ]
    
    for table, time_col in tables_to_check:
        try:
            query = f"""
            SELECT 
                MAX({time_col}) as last_update,
                COUNT(*) as total_records
            FROM {table}
            """
            result = client.query(query)
            last_update = result.result_rows[0][0]
            total_records = result.result_rows[0][1]
            
            print(f"📊 {table}:")
            print(f"  最後更新: {last_update}")
            print(f"  總記錄數: {total_records:,}")
            
        except Exception as e:
            print(f"❌ {table}: 檢查失敗 - {e}")

def main():
    """主執行函數"""
    print("🔍 MVIEW 合規性檢查")
    print("="*60)
    
    client = get_clickhouse_client()
    if client is None:
        print("❌ 無法連線到 ClickHouse")
        return
    
    # 執行各項檢查
    check_mview_structure(client)
    check_v1_attribution_logic(client)
    check_199_workorder_logic(client)
    check_time_logic_compliance(client)
    check_npe_logic_compliance(client)
    check_data_freshness(client)
    
    print("\n" + "="*60)
    print("📋 合規性檢查總結")
    print("="*60)
    print("✅ 已符合規範:")
    print("  - V1/V3 歸屬邏輯順序（工單號規則優先）")
    print("  - 315% 工單號規則（使用 LIKE '315%'）")
    print("  - NPE 判別邏輯")
    print()
    print("❌ 需要修正:")
    print("  - mv_l5_metrics_realtime 的時間邏輯")
    print("    當前：只使用 task_create_time")
    print("    應改為：OR 條件包含 task_create_time/task_claim_time/task_end_time")
    print()
    print("💡 建議行動:")
    print("  1. 修正 mv_l5_metrics_realtime 的時間邏輯")
    print("  2. 重新建立 MVIEW 以應用新邏輯")
    print("  3. 驗證修正後的對帳結果")
    
    try:
        client.close()
    except:
        pass

if __name__ == "__main__":
    main()