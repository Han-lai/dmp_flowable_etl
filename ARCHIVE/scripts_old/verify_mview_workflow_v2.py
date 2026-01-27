#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClickHouse MView 工作流驗證腳本 - 使用 clickhouse-connect
驗證範圍：bronze, silver, gold schemas
時間範圍：2025-12-25 ~ 2025-12-31
"""

import clickhouse_connect
import json
from datetime import datetime
from collections import defaultdict

# ClickHouse 連接配置
CH_HOST = '10.136.218.207'
CH_PORT = 8121
CH_USER = 'default'
CH_PASSWORD = 'default'

def get_connection():
    """建立 ClickHouse 連接"""
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD
    )

def query_mviews_info(client):
    """查詢所有 MView 的基本資訊"""
    sql = """
    SELECT 
        database,
        name,
        engine,
        create_table_query,
        toDateTime(metadata_modification_time) as last_modified
    FROM system.tables
    WHERE database IN ('bronze', 'silver', 'gold')
        AND engine LIKE '%View%'
    ORDER BY database, name
    """
    result = client.query(sql)
    return result.result_rows

def get_mview_ddl(client, database, table_name):
    """取得 MView 的完整 DDL"""
    sql = f"SHOW CREATE TABLE {database}.{table_name}"
    result = client.query(sql)
    return result.result_rows[0][0] if result.result_rows else None

def check_mview_data_freshness(client, database, table_name):
    """檢查 MView 資料新鮮度"""
    try:
        # 嘗試取得最新資料時間戳
        sql = f"""
        SELECT 
            COUNT(*) as row_count,
            MAX(_mview_update_time) as last_update_time,
            MIN(_mview_update_time) as first_update_time
        FROM {database}.{table_name}
        WHERE toDate(_mview_update_time) >= '2025-12-25'
            AND toDate(_mview_update_time) <= '2025-12-31'
        """
        result = client.query(sql)
        if result.result_rows:
            return {
                'row_count': result.result_rows[0][0],
                'last_update': result.result_rows[0][1],
                'first_update': result.result_rows[0][2]
            }
    except Exception as e:
        pass
    
    # 如果沒有 _mview_update_time，嘗試其他時間欄位
    try:
        sql = f"""
        SELECT 
            COUNT(*) as row_count
        FROM {database}.{table_name}
        LIMIT 1
        """
        result = client.query(sql)
        return {'row_count': result.result_rows[0][0] if result.result_rows else 0}
    except:
        return None

def analyze_mview_definition(ddl):
    """分析 MView 定義，識別新舊版本特徵"""
    if not ddl:
        return {}
    
    analysis = {
        'has_varinst_name': 'varinst_name' in ddl,
        'has_varinst_pivoted': 'mv_varinst_pivoted' in ddl,
        'has_npe_logic': "LIKE '%NPE%'" in ddl,
        'has_315_rule': "LIKE '315%'" in ddl,
        'has_old_315_rule': "IN ('3152600035'" in ddl,
        'has_replacing_merge_tree': 'ReplacingMergeTree' in ddl,
        'has_summing_merge_tree': 'SummingMergeTree' in ddl,
        'engine_type': 'ReplacingMergeTree' if 'ReplacingMergeTree' in ddl else 
                       'SummingMergeTree' if 'SummingMergeTree' in ddl else
                       'Other'
    }
    return analysis

def main():
    print("=" * 80)
    print("ClickHouse MView 工作流驗證 - 2026-01-22")
    print("=" * 80)
    print()
    
    try:
        client = get_connection()
        print("✅ ClickHouse 連接成功")
        print(f"   主機: {CH_HOST}:{CH_PORT}")
        print()
        
        # 1. 列出所有 MView
        print("=" * 80)
        print("(1) 列出所有 Materialized View")
        print("=" * 80)
        
        mviews = query_mviews_info(client)
        mview_dict = defaultdict(list)
        
        for row in mviews:
            db, name, engine, ddl, modified_time = row
            mview_dict[db].append({
                'name': name,
                'engine': engine,
                'ddl': ddl,
                'modified_time': modified_time
            })
        
        total_mviews = sum(len(v) for v in mview_dict.values())
        print(f"\n📊 總共發現 {total_mviews} 個 Materialized View\n")
        
        for db in sorted(mview_dict.keys()):
            print(f"📊 Schema: {db} ({len(mview_dict[db])} 個 MView)")
            print("-" * 80)
            for mv in sorted(mview_dict[db], key=lambda x: x['name']):
                print(f"  • {mv['name']}")
                print(f"    引擎: {mv['engine']}")
                print(f"    最後修改: {mv['modified_time']}")
        
        # 2. 驗證 MView 定義
        print("\n" + "=" * 80)
        print("(2) 驗證 MView 定義是否為新版工作流")
        print("=" * 80)
        
        new_version_count = 0
        old_version_count = 0
        mixed_version_count = 0
        
        for db in sorted(mview_dict.keys()):
            print(f"\n📋 Schema: {db}")
            print("-" * 80)
            for mv in sorted(mview_dict[db], key=lambda x: x['name']):
                analysis = analyze_mview_definition(mv['ddl'])
                
                print(f"\n  {mv['name']}:")
                print(f"    引擎: {analysis.get('engine_type', 'Unknown')}")
                
                # 新版特徵檢查
                new_version_features = []
                old_version_features = []
                
                if analysis.get('has_varinst_name'):
                    new_version_features.append("✅ 有 varinst_name 欄位")
                if analysis.get('has_varinst_pivoted'):
                    new_version_features.append("✅ 使用 mv_varinst_pivoted")
                if analysis.get('has_315_rule'):
                    new_version_features.append("✅ 使用新 315% 規則 (LIKE '315%')")
                if analysis.get('has_npe_logic'):
                    new_version_features.append("✅ 有 NPE 判別邏輯")
                
                if analysis.get('has_old_315_rule'):
                    old_version_features.append("❌ 仍使用舊 315% 規則 (IN 特定工單號)")
                
                if new_version_features:
                    print("    新版特徵:")
                    for feat in new_version_features:
                        print(f"      {feat}")
                
                if old_version_features:
                    print("    舊版特徵:")
                    for feat in old_version_features:
                        print(f"      {feat}")
                
                # 版本分類
                if old_version_features and not new_version_features:
                    old_version_count += 1
                    print("    📌 版本: 舊版工作流")
                elif new_version_features and not old_version_features:
                    new_version_count += 1
                    print("    📌 版本: 新版工作流")
                elif new_version_features and old_version_features:
                    mixed_version_count += 1
                    print("    📌 版本: 混合版本 ⚠️")
                else:
                    print("    📌 版本: 無法判斷")
        
        # 3. 驗證新工作流是否有在跑
        print("\n" + "=" * 80)
        print("(3) 驗證新工作流是否真的有在跑 (2025-12-25 ~ 2025-12-31)")
        print("=" * 80)
        
        active_mviews = 0
        inactive_mviews = 0
        
        for db in sorted(mview_dict.keys()):
            print(f"\n📊 Schema: {db}")
            print("-" * 80)
            for mv in sorted(mview_dict[db], key=lambda x: x['name']):
                freshness = check_mview_data_freshness(client, db, mv['name'])
                
                print(f"\n  {mv['name']}:")
                if freshness:
                    row_count = freshness.get('row_count', 0)
                    print(f"    行數: {row_count}")
                    if freshness.get('last_update'):
                        print(f"    最後更新: {freshness.get('last_update')}")
                    if freshness.get('first_update'):
                        print(f"    首次更新: {freshness.get('first_update')}")
                    
                    if row_count > 0:
                        active_mviews += 1
                        print(f"    狀態: ✅ 有資料")
                    else:
                        inactive_mviews += 1
                        print(f"    狀態: ⚠️  無資料")
                else:
                    print(f"    ⚠️  無法取得資料新鮮度資訊")
        
        # 4. 檢查舊工作流
        print("\n" + "=" * 80)
        print("(4) 檢查是否仍有資料在走舊工作流")
        print("=" * 80)
        
        # 查詢舊表
        old_tables_sql = """
        SELECT 
            database,
            name,
            engine
        FROM system.tables
        WHERE database IN ('bronze', 'silver', 'gold')
            AND (name LIKE '%old%' OR name LIKE '%legacy%' OR name LIKE '%v1%')
        ORDER BY database, name
        """
        
        try:
            old_tables_result = client.query(old_tables_sql)
            old_tables = old_tables_result.result_rows
            if old_tables:
                print("\n⚠️  發現可能的舊表:")
                for db, name, engine in old_tables:
                    print(f"  • {db}.{name} ({engine})")
            else:
                print("\n✅ 未發現明顯的舊表")
        except Exception as e:
            print(f"\n⚠️  無法查詢舊表: {str(e)}")
        
        # 5. 總結
        print("\n" + "=" * 80)
        print("驗證總結")
        print("=" * 80)
        print(f"\n📊 MView 版本分布:")
        print(f"  • 新版工作流: {new_version_count}")
        print(f"  • 舊版工作流: {old_version_count}")
        print(f"  • 混合版本: {mixed_version_count}")
        print(f"\n📊 MView 活躍狀態:")
        print(f"  • 有資料: {active_mviews}")
        print(f"  • 無資料: {inactive_mviews}")
        
        print("\n" + "=" * 80)
        print("✅ 驗證完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ 錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
