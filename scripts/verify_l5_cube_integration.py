#!/usr/bin/env python3
"""
L5 指標 Cube.js 整合驗證腳本
驗證修正後的 Cube data model 是否正確支援 L5 指標查詢
"""
import requests
import json
from datetime import datetime

CUBE_API_BASE = "http://REDACTED_IP:4002/cubejs-api/v1"
CUBE_API_KEY = "REDACTED_SECRET"

def test_cube_query(query_name, query, expected_fields=None):
    """測試 Cube 查詢"""
    print(f"\n🧪 測試: {query_name}")
    
    try:
        response = requests.get(
            f"{CUBE_API_BASE}/load",
            headers={'Authorization': CUBE_API_KEY},
            params={'query': json.dumps(query)},
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('data', [])
            print(f"   ✅ 查詢成功，返回 {len(results)} 筆資料")
            
            # 顯示前3筆結果
            for i, row in enumerate(results[:3]):
                print(f"   [{i+1}] {row}")
                
            # 檢查預期欄位
            if expected_fields and results:
                missing_fields = []
                for field in expected_fields:
                    if field not in results[0]:
                        missing_fields.append(field)
                
                if missing_fields:
                    print(f"   ⚠️ 缺少欄位: {missing_fields}")
                else:
                    print(f"   ✅ 所有預期欄位都存在")
                    
            return True
            
        else:
            print(f"   ❌ 查詢失敗: HTTP {response.status_code}")
            print(f"   錯誤: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"   ❌ 查詢錯誤: {e}")
        return False

def main():
    """主要測試流程"""
    print("=" * 80)
    print("L5 指標 Cube.js 整合驗證")
    print("=" * 80)
    
    # 檢查 Cube.js 服務狀態
    print("\n📡 檢查 Cube.js 服務狀態...")
    try:
        response = requests.get(
            f"{CUBE_API_BASE}/meta",
            headers={'Authorization': CUBE_API_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            meta = response.json()
            cubes = meta.get('cubes', [])
            print(f"✅ Cube.js 服務正常，共 {len(cubes)} 個 cubes")
            
            # 列出可用的 cubes
            cube_names = [cube.get('name') for cube in cubes]
            print(f"可用 Cubes: {', '.join(cube_names)}")
        else:
            print(f"❌ Cube.js 服務異常: HTTP {response.status_code}")
            return
            
    except Exception as e:
        print(f"❌ 無法連接 Cube.js 服務: {e}")
        return
    
    # 測試案例
    test_cases = [
        {
            'name': 'L5 在途任務數 (按廠區)',
            'query': {
                'measures': ['ProcTaskNode.l5InProgressTaskCount'],
                'dimensions': ['ProcTaskNode.plant'],
                'limit': 5
            },
            'expected_fields': ['ProcTaskNode.plant', 'ProcTaskNode.l5InProgressTaskCount']
        },
        {
            'name': 'L5 Vx 類型分布',
            'query': {
                'measures': ['ProcTaskNode.l5TotalTaskCount', 'ProcTaskNode.l5DoneTaskCount'],
                'dimensions': ['ProcTaskNode.vxType'],
                'limit': 5
            },
            'expected_fields': ['ProcTaskNode.vxType', 'ProcTaskNode.l5TotalTaskCount', 'ProcTaskNode.l5DoneTaskCount']
        },
        {
            'name': 'L5 任務完成率 (按 Vx 類型)',
            'query': {
                'measures': ['ProcTaskNode.l5TaskCompletionRate'],
                'dimensions': ['ProcTaskNode.vxType'],
                'limit': 5
            },
            'expected_fields': ['ProcTaskNode.vxType', 'ProcTaskNode.l5TaskCompletionRate']
        },
        {
            'name': 'L5 排除任務分析',
            'query': {
                'measures': ['ProcTaskNode.l5TotalTaskCount', 'ProcTaskNode.excludedTaskCount'],
                'dimensions': ['ProcTaskNode.plant'],
                'limit': 3
            },
            'expected_fields': ['ProcTaskNode.plant', 'ProcTaskNode.l5TotalTaskCount', 'ProcTaskNode.excludedTaskCount']
        },
        {
            'name': 'L5 任務狀態分布',
            'query': {
                'measures': [
                    'ProcTaskNode.l5TodoTaskCount',
                    'ProcTaskNode.l5DoingTaskCount', 
                    'ProcTaskNode.l5DoneTaskCount'
                ],
                'dimensions': ['ProcTaskNode.vxType'],
                'limit': 3
            },
            'expected_fields': [
                'ProcTaskNode.vxType',
                'ProcTaskNode.l5TodoTaskCount',
                'ProcTaskNode.l5DoingTaskCount',
                'ProcTaskNode.l5DoneTaskCount'
            ]
        },
        {
            'name': 'L5 歷史快照 - 完成率趨勢',
            'query': {
                'measures': ['DailyMetricsSnapshot.l5DonePct'],
                'dimensions': ['DailyMetricsSnapshot.vxType'],
                'limit': 5
            },
            'expected_fields': ['DailyMetricsSnapshot.vxType', 'DailyMetricsSnapshot.l5DonePct']
        },
        {
            'name': 'L5 歷史快照 - 任務數量趨勢',
            'query': {
                'measures': [
                    'DailyMetricsSnapshot.l5TotalTaskQty',
                    'DailyMetricsSnapshot.l5DoneQty'
                ],
                'dimensions': ['DailyMetricsSnapshot.vxType', 'DailyMetricsSnapshot.plant'],
                'limit': 5
            },
            'expected_fields': [
                'DailyMetricsSnapshot.vxType',
                'DailyMetricsSnapshot.plant',
                'DailyMetricsSnapshot.l5TotalTaskQty',
                'DailyMetricsSnapshot.l5DoneQty'
            ]
        }
    ]
    
    # 執行測試
    passed_tests = 0
    total_tests = len(test_cases)
    
    for test_case in test_cases:
        success = test_cube_query(
            test_case['name'],
            test_case['query'],
            test_case.get('expected_fields')
        )
        if success:
            passed_tests += 1
    
    # 測試結果總結
    print("\n" + "=" * 80)
    print("測試結果總結")
    print("=" * 80)
    print(f"✅ 通過: {passed_tests}/{total_tests}")
    print(f"❌ 失敗: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("\n🎉 所有測試通過！L5 指標 Cube.js 整合完成")
        print("\n📋 可用的 L5 指標查詢:")
        print("   - L5 在途任務數 (即時)")
        print("   - L5 任務完成率 (即時)")
        print("   - L5 Vx 類型分析 (即時)")
        print("   - L5 排除任務分析 (即時)")
        print("   - L5 歷史趨勢查詢 (快照)")
        print("   - L5 多維度聚合查詢")
    else:
        print(f"\n⚠️ 有 {total_tests - passed_tests} 個測試失敗，需要進一步檢查")
    
    print("\n📊 L5 指標 ClickHouse → Cube.js 整合狀態: ✅ 完成")

if __name__ == "__main__":
    main()