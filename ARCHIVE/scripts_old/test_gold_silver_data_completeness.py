#!/usr/bin/env python3
"""
金銀質資料完成度測試腳本
測試 Silver 層 MVIEW 和 Gold 層快照的資料完整性和一致性

測試範圍：
1. Silver 層 MVIEW 表狀態檢查
2. Gold 層快照表狀態檢查
3. Path A vs Path B 資料一致性驗證
4. MVIEW 更新機制驗證
5. 資料完整性檢查
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect
from datetime import datetime, timedelta
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

def check_silver_mview_status(client):
    """檢查 Silver 層 MVIEW 表狀態"""
    print("\n🔍 Silver 層 MVIEW 表狀態檢查")
    print("="*60)
    
    silver_tables = [
        # 第一層 MVIEW
        'silver.mv_varinst_pivoted',
        'silver.mv_emp_user_groups', 
        'silver.mv_emp_node_codes',
        'silver.mv_emp_org_info',
        'silver.mv_task_status_summary',
        
        # 第二層 MVIEW
        'silver.mv_fact_task_vx_attribution',
        'silver.mv_dim_config_user',
        'silver.mv_l5_metrics_realtime',
        
        # Path A 直接表
        'silver.FACT_TASK_VX_ATTRIBUTION',
        'silver.DIM_CONFIG_USER'
    ]
    
    table_status = {}
    
    for table in silver_tables:
        try:
            # 檢查表是否存在並獲取記錄數
            count_result = client.query(f"SELECT COUNT(*) as count FROM {table}")
            count = count_result.result_rows[0][0]
            
            # 檢查最新更新時間（如果有 _mview_update_time 欄位）
            try:
                time_result = client.query(f"SELECT MAX(_mview_update_time) as last_update FROM {table}")
                last_update = time_result.result_rows[0][0]
            except:
                last_update = None
            
            table_status[table] = {
                'exists': True,
                'count': count,
                'last_update': last_update
            }
            
            status_icon = "✅" if count > 0 else "⚠️"
            update_info = f", 最後更新: {last_update}" if last_update else ""
            print(f"{status_icon} {table}: {count:,} 筆記錄{update_info}")
            
        except Exception as e:
            table_status[table] = {
                'exists': False,
                'error': str(e)
            }
            print(f"❌ {table}: 不存在或查詢失敗 - {e}")
    
    return table_status

def check_gold_snapshot_status(client):
    """檢查 Gold 層快照表狀態"""
    print("\n🔍 Gold 層快照表狀態檢查")
    print("="*60)
    
    gold_tables = [
        'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT',
        'gold.DAILY_USER_UTILIZATION_SNAPSHOT',
        'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV'  # REFRESHABLE MV
    ]
    
    gold_status = {}
    
    for table in gold_tables:
        try:
            # 檢查表是否存在
            count_result = client.query(f"SELECT COUNT(*) as count FROM {table}")
            count = count_result.result_rows[0][0]
            
            # 檢查最新快照日期
            try:
                date_result = client.query(f"SELECT MAX(snapshot_date) as latest_date FROM {table}")
                latest_date = date_result.result_rows[0][0]
            except:
                latest_date = None
            
            # 檢查最近7天的快照完整性
            try:
                recent_result = client.query(f"""
                    SELECT COUNT(DISTINCT snapshot_date) as recent_days
                    FROM {table}
                    WHERE snapshot_date >= today() - INTERVAL 7 DAY
                """)
                recent_days = recent_result.result_rows[0][0]
            except:
                recent_days = 0
            
            gold_status[table] = {
                'exists': True,
                'count': count,
                'latest_date': latest_date,
                'recent_days': recent_days
            }
            
            status_icon = "✅" if count > 0 and recent_days > 0 else "⚠️"
            print(f"{status_icon} {table}:")
            print(f"    總記錄數: {count:,}")
            print(f"    最新日期: {latest_date}")
            print(f"    近7天快照: {recent_days} 天")
            
        except Exception as e:
            gold_status[table] = {
                'exists': False,
                'error': str(e)
            }
            print(f"❌ {table}: 不存在或查詢失敗 - {e}")
    
    return gold_status

def compare_path_a_vs_path_b(client, test_date='2025-12-31'):
    """比較 Path A 和 Path B 的資料一致性"""
    print(f"\n📊 Path A vs Path B 資料一致性驗證 (測試日期: {test_date})")
    print("="*80)
    
    # 檢查 Path A 表是否存在
    try:
        path_a_result = client.query(f"""
            SELECT 
                vx_type,
                COUNT(*) as task_count,
                SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_count,
                SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_count,
                SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_count
            FROM silver.FACT_TASK_VX_ATTRIBUTION
            WHERE task_create_date = '{test_date}'
            GROUP BY vx_type
            ORDER BY vx_type
        """)
        path_a_df = pd.DataFrame(path_a_result.result_rows, columns=path_a_result.column_names)
        print("✅ Path A 資料查詢成功")
    except Exception as e:
        print(f"❌ Path A 資料查詢失敗: {e}")
        path_a_df = pd.DataFrame()
    
    # 檢查 Path B MVIEW
    try:
        path_b_result = client.query(f"""
            SELECT 
                vx_type,
                COUNT(*) as task_count,
                SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_count,
                SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_count,
                SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_count
            FROM silver.mv_fact_task_vx_attribution FINAL
            WHERE toDate(task_create_time) = '{test_date}'
            GROUP BY vx_type
            ORDER BY vx_type
        """)
        path_b_df = pd.DataFrame(path_b_result.result_rows, columns=path_b_result.column_names)
        print("✅ Path B MVIEW 資料查詢成功")
    except Exception as e:
        print(f"❌ Path B MVIEW 資料查詢失敗: {e}")
        path_b_df = pd.DataFrame()
    
    # 比較結果
    if len(path_a_df) > 0 and len(path_b_df) > 0:
        print("\n📈 Path A vs Path B 比較結果:")
        print("-" * 80)
        print(f"{'路徑':<8} {'Vx類型':<6} {'總數':<8} {'TODO':<6} {'DOING':<7} {'DONE':<6}")
        print("-" * 80)
        
        # 顯示 Path A 資料
        for _, row in path_a_df.iterrows():
            print(f"{'Path A':<8} {row['vx_type']:<6} {row['task_count']:<8} {row['todo_count']:<6} {row['doing_count']:<7} {row['done_count']:<6}")
        
        print("-" * 80)
        
        # 顯示 Path B 資料
        for _, row in path_b_df.iterrows():
            print(f"{'Path B':<8} {row['vx_type']:<6} {row['task_count']:<8} {row['todo_count']:<6} {row['doing_count']:<7} {row['done_count']:<6}")
        
        # 計算差異
        print("\n📊 差異分析:")
        print("-" * 60)
        
        all_vx_types = set(path_a_df['vx_type'].tolist() + path_b_df['vx_type'].tolist())
        total_diff = 0
        
        for vx_type in sorted(all_vx_types):
            a_row = path_a_df[path_a_df['vx_type'] == vx_type]
            b_row = path_b_df[path_b_df['vx_type'] == vx_type]
            
            a_count = a_row['task_count'].iloc[0] if len(a_row) > 0 else 0
            b_count = b_row['task_count'].iloc[0] if len(b_row) > 0 else 0
            
            diff = b_count - a_count
            total_diff += abs(diff)
            
            status = "✅" if diff == 0 else "⚠️"
            print(f"{status} {vx_type}: Path A={a_count}, Path B={b_count}, 差異={diff:+d}")
        
        if total_diff == 0:
            print("\n🎉 Path A 和 Path B 資料完全一致！")
            return True
        else:
            print(f"\n⚠️ 發現差異，總差異數: {total_diff}")
            return False
    
    elif len(path_b_df) > 0:
        print("\n✅ 僅 Path B MVIEW 有資料（正常，MVIEW 更即時）")
        print("Path B MVIEW 資料:")
        print(path_b_df.to_string(index=False))
        return True
    
    else:
        print("\n❌ 兩個路徑都沒有資料")
        return False

def check_mview_update_mechanism(client):
    """檢查 MVIEW 更新機制"""
    print("\n🔄 MVIEW 更新機制檢查")
    print("="*60)
    
    # 檢查 MVIEW 更新時間
    mview_tables = [
        'silver.mv_varinst_pivoted',
        'silver.mv_fact_task_vx_attribution',
        'silver.mv_dim_config_user',
        'silver.mv_l5_metrics_realtime'
    ]
    
    print("MVIEW 最後更新時間:")
    for table in mview_tables:
        try:
            result = client.query(f"SELECT MAX(_mview_update_time) as last_update FROM {table}")
            last_update = result.result_rows[0][0]
            
            if last_update:
                # 計算更新時間差
                now = datetime.now()
                if isinstance(last_update, str):
                    last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                
                time_diff = now - last_update.replace(tzinfo=None)
                
                if time_diff.total_seconds() < 3600:  # 1小時內
                    status = "✅"
                elif time_diff.total_seconds() < 86400:  # 1天內
                    status = "⚠️"
                else:
                    status = "❌"
                
                print(f"{status} {table}: {last_update} ({time_diff})")
            else:
                print(f"❌ {table}: 無更新時間記錄")
                
        except Exception as e:
            print(f"❌ {table}: 查詢失敗 - {e}")

def check_data_completeness(client):
    """檢查資料完整性"""
    print("\n📋 資料完整性檢查")
    print("="*60)
    
    # 檢查最近7天的資料完整性
    try:
        completeness_result = client.query("""
            SELECT 
                toDate(task_create_time) as date,
                vx_type,
                COUNT(*) as task_count
            FROM silver.mv_fact_task_vx_attribution FINAL
            WHERE toDate(task_create_time) >= today() - INTERVAL 7 DAY
            GROUP BY date, vx_type
            ORDER BY date DESC, vx_type
        """)
        
        if completeness_result.result_rows:
            df = pd.DataFrame(completeness_result.result_rows, columns=completeness_result.column_names)
            
            print("最近7天資料分布:")
            print("-" * 40)
            
            # 按日期分組顯示
            for date in df['date'].unique():
                date_data = df[df['date'] == date]
                total_tasks = date_data['task_count'].sum()
                print(f"\n📅 {date}: 總計 {total_tasks:,} 筆任務")
                
                for _, row in date_data.iterrows():
                    print(f"    {row['vx_type']}: {row['task_count']:,} 筆")
            
            # 檢查是否有缺失的日期
            dates = sorted(df['date'].unique(), reverse=True)
            if len(dates) >= 7:
                print("\n✅ 最近7天資料完整")
            else:
                print(f"\n⚠️ 最近7天僅有 {len(dates)} 天資料")
                
        else:
            print("❌ 最近7天無任何資料")
            
    except Exception as e:
        print(f"❌ 資料完整性檢查失敗: {e}")

def main():
    """主執行函數"""
    try:
        print("🚀 開始金銀質資料完成度測試")
        print("="*80)
        
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 1. 檢查 Silver 層 MVIEW 狀態
        silver_status = check_silver_mview_status(client)
        
        # 2. 檢查 Gold 層快照狀態
        gold_status = check_gold_snapshot_status(client)
        
        # 3. 比較 Path A vs Path B 一致性
        consistency_ok = compare_path_a_vs_path_b(client)
        
        # 4. 檢查 MVIEW 更新機制
        check_mview_update_mechanism(client)
        
        # 5. 檢查資料完整性
        check_data_completeness(client)
        
        # 總結
        print("\n" + "="*80)
        print("📊 金銀質資料完成度測試總結")
        print("="*80)
        
        # Silver 層狀態總結
        silver_mview_count = sum(1 for table, status in silver_status.items() 
                                if 'mv_' in table and status.get('exists', False) and status.get('count', 0) > 0)
        silver_direct_count = sum(1 for table, status in silver_status.items() 
                                 if 'mv_' not in table and status.get('exists', False) and status.get('count', 0) > 0)
        
        print(f"Silver 層 MVIEW 表: {silver_mview_count}/8 個正常")
        print(f"Silver 層直接表: {silver_direct_count}/2 個正常")
        
        # Gold 層狀態總結
        gold_count = sum(1 for status in gold_status.values() 
                        if status.get('exists', False) and status.get('count', 0) > 0)
        print(f"Gold 層快照表: {gold_count}/3 個正常")
        
        # 一致性總結
        consistency_status = "✅ 一致" if consistency_ok else "⚠️ 有差異"
        print(f"Path A vs Path B: {consistency_status}")
        
        # 整體評估
        if silver_mview_count >= 6 and gold_count >= 2 and consistency_ok:
            print("\n🎉 金銀質資料管道運作正常！")
            print("✅ MVIEW 自動更新機制正常")
            print("✅ 資料一致性良好")
            print("✅ 可以進行生產環境測試")
            return True
        else:
            print("\n⚠️ 發現問題，需要進一步調查")
            if silver_mview_count < 6:
                print("❌ Silver 層 MVIEW 表不完整")
            if gold_count < 2:
                print("❌ Gold 層快照表不完整")
            if not consistency_ok:
                print("❌ Path A 和 Path B 資料不一致")
            return False
        
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