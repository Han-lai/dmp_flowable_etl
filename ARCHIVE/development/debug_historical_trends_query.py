#!/usr/bin/env python3
"""
Debug Historical Trends 查詢
模擬 Superset 透過 Cube.js 的查詢條件，確認實際 SQL 和結果
"""
import requests
import json
from datetime import datetime, timedelta

CUBE_API_BASE = "http://REDACTED_IP:4002/cubejs-api/v1"
CUBE_API_KEY = "REDACTED_SECRET"

def query_cube_api_with_debug(query, description=""):
    """查詢 Cube API 並返回結果，包含 SQL debug 資訊"""
    try:
        # 先查詢 SQL
        sql_response = requests.get(
            f"{CUBE_API_BASE}/sql",
            headers={'Authorization': CUBE_API_KEY},
            params={'query': json.dumps(query)},
            timeout=20
        )
        
        print(f"\n🔍 {description}")
        print("=" * 60)
        
        if sql_response.status_code == 200:
            sql_data = sql_response.json()
            print("📋 實際產生的 SQL:")
            for sql_item in sql_data.get('sql', []):
                print(f"   {sql_item['sql']}")
        else:
            print(f"❌ SQL 查詢失敗: HTTP {sql_response.status_code}")
        
        # 再查詢實際資料
        response = requests.get(
            f"{CUBE_API_BASE}/load",
            headers={'Authorization': CUBE_API_KEY},
            params={'query': json.dumps(query)},
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('data', [])
            print(f"\n📊 查詢結果: {len(results)} 筆資料")
            
            for i, row in enumerate(results):
                print(f"   [{i+1}] {row}")
                
            return results
        else:
            print(f"❌ 資料查詢失敗: HTTP {response.status_code}")
            print(f"   錯誤: {response.text[:300]}...")
            return None
            
    except Exception as e:
        print(f"❌ 查詢錯誤: {e}")
        return None

def main():
    """Debug Historical Trends 查詢"""
    print("=" * 80)
    print("Debug Historical Trends 查詢")
    print("=" * 80)
    
    # 模擬 Superset 的查詢條件
    query_conditions = {
        'measures': ['HistoricalTrends.l5TotalTaskQty'],
        'timeDimensions': [{
            'dimension': 'HistoricalTrends.snapshotDate',
            'granularity': 'day'
        }],
        'dimensions': [
            'HistoricalTrends.vxType',
            'HistoricalTrends.plant', 
            'HistoricalTrends.factory',
            'HistoricalTrends.line'
        ],
        'filters': [
            {
                'member': 'HistoricalTrends.vxType',
                'operator': 'equals',
                'values': ['V1']
            },
            {
                'member': 'HistoricalTrends.plant',
                'operator': 'equals',
                'values': ['WJ2']
            },
            {
                'member': 'HistoricalTrends.factory',
                'operator': 'equals',
                'values': ['NBU']
            },
            {
                'member': 'HistoricalTrends.line',
                'operator': 'equals',
                'values': ['E5']
            }
        ],
        'order': {'HistoricalTrends.snapshotDate': 'asc'}
    }
    
    results = query_cube_api_with_debug(query_conditions, "Historical Trends 查詢 (模擬 Superset)")
    
    # 檢查 Gold 層原始資料
    print("\n" + "=" * 80)
    print("檢查 Gold 層原始資料")
    print("=" * 80)
    
    query_gold_raw = {
        'measures': ['DailyMetricsSnapshot.l5TotalTaskQty'],
        'dimensions': [
            'DailyMetricsSnapshot.snapshotDate',
            'DailyMetricsSnapshot.vxType',
            'DailyMetricsSnapshot.plant',
            'DailyMetricsSnapshot.factory',
            'DailyMetricsSnapshot.line'
        ],
        'filters': [
            {
                'member': 'DailyMetricsSnapshot.vxType',
                'operator': 'equals',
                'values': ['V1']
            },
            {
                'member': 'DailyMetricsSnapshot.plant',
                'operator': 'equals',
                'values': ['WJ2']
            },
            {
                'member': 'DailyMetricsSnapshot.factory',
                'operator': 'equals',
                'values': ['NBU']
            },
            {
                'member': 'DailyMetricsSnapshot.line',
                'operator': 'equals',
                'values': ['E5']
            }
        ],
        'order': {'DailyMetricsSnapshot.snapshotDate': 'asc'}
    }
    
    results_gold = query_cube_api_with_debug(query_gold_raw, "Gold 層原始資料查詢")
    
    # 檢查是否有其他日期的資料
    print("\n" + "=" * 80)
    print("檢查相同條件下所有日期的資料")
    print("=" * 80)
    
    query_all_dates = {
        'measures': ['DailyMetricsSnapshot.l5TotalTaskQty'],
        'dimensions': [
            'DailyMetricsSnapshot.snapshotDate'
        ],
        'filters': [
            {
                'member': 'DailyMetricsSnapshot.vxType',
                'operator': 'equals',
                'values': ['V1']
            },
            {
                'member': 'DailyMetricsSnapshot.plant',
                'operator': 'equals',
                'values': ['WJ2']
            },
            {
                'member': 'DailyMetricsSnapshot.factory',
                'operator': 'equals',
                'values': ['NBU']
            },
            {
                'member': 'DailyMetricsSnapshot.line',
                'operator': 'equals',
                'values': ['E5']
            }
        ],
        'order': {'DailyMetricsSnapshot.snapshotDate': 'asc'}
    }
    
    results_dates = query_cube_api_with_debug(query_all_dates, "所有日期資料檢查")

if __name__ == "__main__":
    main()