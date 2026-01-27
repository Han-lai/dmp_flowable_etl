#!/usr/bin/env python3
"""
驗證 Cube.js 與 ClickHouse 原始資料的一致性
針對 V1 + WJ2 + NBU + E5 條件進行比對
"""
import requests
import json
import clickhouse_connect

CUBE_API_BASE = "http://10.136.218.207:4002/cubejs-api/v1"
CUBE_API_KEY = "dmp_flowable_cube_secret_key_2026"

# ClickHouse 連接設定
CH_HOST = "localhost"
CH_PORT = 8123
CH_USER = "default"
CH_PASSWORD = ""

def query_cube_api(query, description=""):
    """查詢 Cube API"""
    try:
        response = requests.get(
            f"{CUBE_API_BASE}/load",
            headers={'Authorization': CUBE_API_KEY},
            params={'query': json.dumps(query)},
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            print(f"❌ Cube API 查詢失敗: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Cube API 查詢錯誤: {e}")
        return None

def query_clickhouse(sql, description=""):
    """查詢 ClickHouse"""
    try:
        client = clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            username=CH_USER,
            password=CH_PASSWORD
        )
        
        result = client.query(sql)
        return result.result_rows
        
    except Exception as e:
        print(f"❌ ClickHouse 查詢錯誤 ({description}): {e}")
        return None

def main():
    """主要驗證流程"""
    print("=" * 80)
    print("Cube.js vs ClickHouse 資料一致性驗證")
    print("條件: V1 + WJ2 + NBU + E5")
    print("=" * 80)
    
    # 1. 查詢 Cube.js DailyMetricsSnapshot
    print("\n📊 1. Cube.js DailyMetricsSnapshot 查詢")
    print("-" * 50)
    
    cube_query = {
        'measures': [
            'DailyMetricsSnapshot.l5TotalTaskQty',
            'DailyMetricsSnapshot.l5TodoQty',
            'DailyMetricsSnapshot.l5DoingQty',
            'DailyMetricsSnapshot.l5DoneQty'
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
    
    cube_results = query_cube_api(cube_query, "DailyMetricsSnapshot")
    if cube_results:
        print(f"   Cube.js 返回 {len(cube_results)} 筆資料:")
        for row in cube_results:
            date = row.get('DailyMetricsSnapshot.snapshotDate', 'N/A')
            period = row.get('DailyMetricsSnapshot.timePeriodType', 'N/A')
            total = row.get('DailyMetricsSnapshot.l5TotalTaskQty', 0)
            todo = row.get('DailyMetricsSnapshot.l5TodoQty', 0)
            doing = row.get('DailyMetricsSnapshot.l5DoingQty', 0)
            done = row.get('DailyMetricsSnapshot.l5DoneQty', 0)
            print(f"   {date} ({period}): 總數={total}, TODO={todo}, DOING={doing}, DONE={done}")
    
    # 2. 查詢 ClickHouse Gold 層原始資料
    print("\n📊 2. ClickHouse Gold 層原始資料")
    print("-" * 50)
    
    ch_sql_gold = """
    SELECT 
        snapshot_date,
        time_period_type,
        total_task_qty,
        todo_qty,
        doing_qty,
        done_qty
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE vx_type = 'V1'
      AND plant = 'WJ2' 
      AND factory = 'NBU'
      AND line = 'E5'
    ORDER BY snapshot_date, time_period_type
    """
    
    ch_results_gold = query_clickhouse(ch_sql_gold, "Gold 層")
    if ch_results_gold:
        print(f"   ClickHouse Gold 層 {len(ch_results_gold)} 筆資料:")
        for row in ch_results_gold:
            date, period, total, todo, doing, done = row
            print(f"   {date} ({period}): 總數={total}, TODO={todo}, DOING={doing}, DONE={done}")
    
    # 3. 查詢 ClickHouse Silver 層原始資料 (驗證來源)
    print("\n📊 3. ClickHouse Silver 層原始資料驗證")
    print("-" * 50)
    
    ch_sql_silver = """
    SELECT 
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_tasks,
        SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks,
        toDate(task_create_time) as create_date
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
      AND is_excluded = 0
    GROUP BY toDate(task_create_time)
    ORDER BY create_date
    """
    
    ch_results_silver = query_clickhouse(ch_sql_silver, "Silver 層")
    if ch_results_silver:
        print(f"   ClickHouse Silver 層 {len(ch_results_silver)} 筆資料:")
        for row in ch_results_silver:
            total, todo, doing, done, date = row
            print(f"   {date}: 總數={total}, TODO={todo}, DOING={doing}, DONE={done}")
    
    # 4. 檢查 Gold 層快照邏輯
    print("\n📊 4. 檢查 Gold 層快照建立邏輯")
    print("-" * 50)
    
    ch_sql_snapshot_logic = """
    SELECT 
        snapshot_date,
        time_period_type,
        COUNT(*) as record_count,
        SUM(total_task_qty) as sum_total,
        SUM(done_qty) as sum_done
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    GROUP BY snapshot_date, time_period_type
    ORDER BY snapshot_date, time_period_type
    """
    
    ch_results_logic = query_clickhouse(ch_sql_snapshot_logic, "快照邏輯")
    if ch_results_logic:
        print(f"   Gold 層快照聚合結果:")
        for row in ch_results_logic:
            date, period, count, total, done = row
            print(f"   {date} ({period}): {count}筆記錄, 總數={total}, 完成={done}")
    
    # 5. 比對結果分析
    print("\n📊 5. 比對結果分析")
    print("-" * 50)
    
    if cube_results and ch_results_gold:
        print("   🔍 Cube.js vs ClickHouse Gold 層比對:")
        
        # 建立 Gold 層資料字典
        gold_dict = {}
        for row in ch_results_gold:
            date, period, total, todo, doing, done = row
            key = f"{date}_{period}"
            gold_dict[key] = {'total': total, 'todo': todo, 'doing': doing, 'done': done}
        
        # 比對 Cube.js 結果
        for cube_row in cube_results:
            date = cube_row.get('DailyMetricsSnapshot.snapshotDate', 'N/A')
            period = cube_row.get('DailyMetricsSnapshot.timePeriodType', 'N/A')
            key = f"{date}_{period}"
            
            cube_total = int(cube_row.get('DailyMetricsSnapshot.l5TotalTaskQty', 0))
            cube_done = int(cube_row.get('DailyMetricsSnapshot.l5DoneQty', 0))
            
            if key in gold_dict:
                gold_total = gold_dict[key]['total']
                gold_done = gold_dict[key]['done']
                
                total_match = cube_total == gold_total
                done_match = cube_done == gold_done
                
                print(f"   {date} ({period}):")
                print(f"     總數: Cube={cube_total}, Gold={gold_total} {'✅' if total_match else '❌'}")
                print(f"     完成: Cube={cube_done}, Gold={gold_done} {'✅' if done_match else '❌'}")
            else:
                print(f"   {date} ({period}): ❌ Gold 層找不到對應資料")
    
    # 6. 結論
    print("\n📊 6. 結論與建議")
    print("-" * 50)
    
    print("   🎯 關鍵發現:")
    print("   1. 時間維度: Gold 層使用 snapshot_date")
    print("   2. 資料粒度: 按 time_period_type 分組 (day/week/month)")
    print("   3. 篩選條件: vx_type + plant + factory + line")
    
    if cube_results and len(cube_results) == 3:
        print("   4. ✅ 資料完整性: 包含 day/week/month 三種粒度")
    else:
        print("   4. ⚠️ 資料完整性: 可能缺少某些時間粒度")
    
    print("\n   💡 建議:")
    print("   - 如果數值不符預期，檢查 Gold 層快照建立邏輯")
    print("   - 確認 time_period_type 篩選是否正確")
    print("   - 驗證 Silver 層來源資料的準確性")

if __name__ == "__main__":
    main()