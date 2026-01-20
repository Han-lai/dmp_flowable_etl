#!/usr/bin/env python3
"""
獲取 Cube.js 實際產生的 SQL
模擬 Historical Trends 查詢
"""
import requests
import json

CUBE_API_BASE = "http://REDACTED_IP:4002/cubejs-api/v1"
CUBE_API_KEY = "REDACTED_SECRET"

def get_cube_sql(query, description=""):
    """獲取 Cube.js 產生的 SQL"""
    try:
        # 使用 /sql endpoint 獲取 SQL
        response = requests.get(
            f"{CUBE_API_BASE}/sql",
            headers={'Authorization': CUBE_API_KEY},
            params={'query': json.dumps(query)},
            timeout=20
        )
        
        print(f"\n🔍 {description}")
        print("=" * 60)
        
        if response.status_code == 200:
            data = response.json()
            
            print("📋 完整 API 回應:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            sql_items = data.get('sql', [])
            
            if sql_items and len(sql_items) > 0:
                print("\n📋 Cube.js 產生的 SQL:")
                for i, sql_item in enumerate(sql_items, 1):
                    print(f"\n[SQL {i}]")
                    if isinstance(sql_item, dict):
                        print(sql_item.get('sql', 'No SQL found'))
                    else:
                        print(sql_item)
            else:
                print("⚠️ 未找到 SQL 內容")
                
            return sql_items
        else:
            print(f"❌ SQL 查詢失敗: HTTP {response.status_code}")
            print(f"錯誤: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 查詢錯誤: {e}")
        return None

def main():
    """獲取 Historical Trends 的 SQL"""
    print("=" * 80)
    print("Cube.js Historical Trends SQL 分析")
    print("=" * 80)
    
    # 模擬 Playground 的查詢
    query = {
        'measures': [
            'HistoricalTrends.l5TotalTaskQty',
            'HistoricalTrends.l5TodoQty',
            'HistoricalTrends.l5DoingQty',
            'HistoricalTrends.l5DoneQty'
        ],
        'timeDimensions': [{
            'dimension': 'HistoricalTrends.snapshotDate',
            'granularity': 'day'
        }],
        'dimensions': [
            'HistoricalTrends.vxType',
            'HistoricalTrends.plant',
            'HistoricalTrends.factory',
            'HistoricalTrends.line',
            'HistoricalTrends.timePeriodType'
        ],
        'filters': [
            {'member': 'HistoricalTrends.vxType', 'operator': 'equals', 'values': ['V1']},
            {'member': 'HistoricalTrends.plant', 'operator': 'equals', 'values': ['WJ2']},
            {'member': 'HistoricalTrends.factory', 'operator': 'equals', 'values': ['NBU']},
            {'member': 'HistoricalTrends.line', 'operator': 'equals', 'values': ['E5']}
        ],
        'order': {'HistoricalTrends.snapshotDate': 'asc'}
    }
    
    sql_result = get_cube_sql(query, "Historical Trends 查詢")
    
    # 也測試直接查詢 DailyMetricsSnapshot
    query_direct = {
        'measures': [
            'DailyMetricsSnapshot.l5TotalTaskQty'
        ],
        'dimensions': [
            'DailyMetricsSnapshot.snapshotDate',
            'DailyMetricsSnapshot.timePeriodType'
        ],
        'filters': [
            {'member': 'DailyMetricsSnapshot.vxType', 'operator': 'equals', 'values': ['V1']},
            {'member': 'DailyMetricsSnapshot.plant', 'operator': 'equals', 'values': ['WJ2']},
            {'member': 'DailyMetricsSnapshot.factory', 'operator': 'equals', 'values': ['NBU']},
            {'member': 'DailyMetricsSnapshot.line', 'operator': 'equals', 'values': ['E5']}
        ],
        'order': {'DailyMetricsSnapshot.snapshotDate': 'asc'}
    }
    
    sql_result_direct = get_cube_sql(query_direct, "DailyMetricsSnapshot 直接查詢")
    
    print("\n" + "=" * 80)
    print("SQL 分析總結")
    print("=" * 80)
    print("🎯 關鍵檢查點:")
    print("1. 時間維度使用的欄位 (snapshot_date)")
    print("2. 是否有隱含的時間篩選條件")
    print("3. JOIN 邏輯是否正確")
    print("4. WHERE 條件是否完整")

if __name__ == "__main__":
    main()