"""
驗證腳本: 執行 06_validation.sql 並格式化輸出結果
"""
import clickhouse_connect

CH_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def run_validation():
    print("=" * 60)
    print("資料流重建驗證")
    print("=" * 60)
    
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # 1. 總覽：各層資料量
    print("\n📊 1. 各層資料量總覽")
    print("-" * 40)
    queries = [
        ("Bronze bpm_act_hi_taskinst", "SELECT count() FROM bronze.bpm_act_hi_taskinst"),
        ("Silver mv_varinst_pivoted", "SELECT count() FROM silver.mv_varinst_pivoted"),
        ("Silver mv_dim_mfg_five_level", "SELECT count() FROM silver.mv_dim_mfg_five_level"),
        ("Silver mv_fact_task_vx", "SELECT count() FROM silver.mv_fact_task_vx"),
        ("Gold rmv_l5_task_completion", "SELECT count() FROM gold.rmv_l5_task_completion"),
        ("Gold rmv_user_utilization", "SELECT count() FROM gold.rmv_user_utilization"),
    ]
    for name, sql in queries:
        try:
            result = client.query(sql)
            count = result.result_rows[0][0]
            status = "✅" if count > 0 else "⚠️"
            print(f"  {status} {name}: {count:,} 筆")
        except Exception as e:
            print(f"  ❌ {name}: 錯誤 - {e}")
    
    # 2. Vx 分布
    print("\n📊 2. Vx 類型分布")
    print("-" * 40)
    result = client.query("""
        SELECT vx_type, count() AS cnt 
        FROM silver.mv_fact_task_vx FINAL
        GROUP BY vx_type 
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"  {row[0]}: {row[1]:,}")
    
    # 3. 維度來源分布
    print("\n📊 3. 維度來源分布")
    print("-" * 40)
    result = client.query("""
        SELECT region_source, count() AS cnt,
               round(count() * 100.0 / sum(count()) OVER (), 2) AS pct
        FROM silver.mv_fact_task_vx FINAL
        GROUP BY region_source
        ORDER BY cnt DESC
    """)
    for row in result.result_rows:
        print(f"  {row[0]}: {row[1]:,} ({row[2]}%)")
    
    # 4. Gold 層 REFRESHABLE MView 狀態
    print("\n📊 4. REFRESHABLE MView 狀態")
    print("-" * 40)
    try:
        result = client.query("""
            SELECT view, status, 
                   last_refresh_time, next_refresh_time,
                   last_refresh_result
            FROM system.view_refreshes
            WHERE database = 'gold'
        """)
        if result.result_rows:
            for row in result.result_rows:
                print(f"  📌 {row[0]}")
                print(f"     狀態: {row[1]}")
                print(f"     上次刷新: {row[2]}")
                print(f"     下次刷新: {row[3]}")
                print(f"     結果: {row[4]}")
        else:
            print("  ⚠️ 沒有找到 REFRESHABLE MView 狀態")
    except Exception as e:
        print(f"  ❌ 查詢失敗: {e}")
    
    # 5. 資料延遲檢查
    print("\n📊 5. 資料延遲檢查")
    print("-" * 40)
    delay_queries = [
        ("silver.mv_varinst_pivoted", "SELECT max(_mview_update_time), dateDiff('minute', max(_mview_update_time), now()) FROM silver.mv_varinst_pivoted"),
        ("silver.mv_fact_task_vx", "SELECT max(_mview_update_time), dateDiff('minute', max(_mview_update_time), now()) FROM silver.mv_fact_task_vx"),
    ]
    for name, sql in delay_queries:
        try:
            result = client.query(sql)
            last_update, delay = result.result_rows[0]
            status = "✅" if delay < 60 else "⚠️"
            print(f"  {status} {name}")
            print(f"     最後更新: {last_update}")
            print(f"     延遲: {delay} 分鐘")
        except Exception as e:
            print(f"  ❌ {name}: 錯誤 - {e}")
    
    # 6. 抽樣驗證 (CNE WJ2 NBU)
    print("\n📊 6. 抽樣驗證 (CNE WJ2)")
    print("-" * 40)
    result = client.query("""
        SELECT vx_type, task_status, count() AS cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE region = 'CNE' AND plant = 'WJ2'
        GROUP BY vx_type, task_status
        ORDER BY vx_type, task_status
        LIMIT 20
    """)
    print(f"  {'Vx':<6} {'狀態':<8} {'數量':>10}")
    print(f"  {'-'*6} {'-'*8} {'-'*10}")
    for row in result.result_rows:
        print(f"  {row[0]:<6} {row[1]:<8} {row[2]:>10,}")
    
    print("\n" + "=" * 60)
    print("✅ 驗證完成！")
    print("=" * 60)
    print("\n下一步: 確認無誤後執行 05_cleanup_path_a.sql 清理舊表")

if __name__ == '__main__':
    run_validation()
