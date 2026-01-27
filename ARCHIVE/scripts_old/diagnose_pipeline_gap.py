#!/usr/bin/env python3
"""
診斷 Pipeline 缺失原因
檢查 Silver → Gold 層的資料流程哪一段沒有接好
"""
import clickhouse_connect
import os
import glob

# ClickHouse 連接設定
CH_HOST = "REDACTED_IP"
CH_PORT = 8121
CH_USER = "default"
CH_PASSWORD = "default"

def query_clickhouse(sql, description=""):
    """查詢 ClickHouse"""
    try:
        client = clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            username=CH_USER,
            password=CH_PASSWORD
        )
        
        print(f"\n🔍 {description}")
        print("-" * 60)
        
        result = client.query(sql)
        return result.result_rows
        
    except Exception as e:
        print(f"❌ ClickHouse 查詢錯誤: {e}")
        return None

def check_sql_files():
    """檢查 SQL 檔案中的 Gold 層建立邏輯"""
    print("\n🔍 檢查 SQL 檔案中的 Gold 層建立邏輯")
    print("-" * 60)
    
    # 搜尋 SQL 檔案
    sql_patterns = [
        "sql/*.sql",
        "scripts/*.sql", 
        "**/*gold*.sql",
        "**/*snapshot*.sql",
        "**/*daily*.sql"
    ]
    
    found_files = []
    for pattern in sql_patterns:
        files = glob.glob(pattern, recursive=True)
        found_files.extend(files)
    
    # 去重
    found_files = list(set(found_files))
    
    print(f"找到 {len(found_files)} 個 SQL 檔案:")
    for file in found_files:
        print(f"  📄 {file}")
        
        # 檢查檔案內容是否包含 Gold 層相關關鍵字
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read().upper()
                
            keywords = ['DAILY_L5_TASK_COMPLETION_SNAPSHOT', 'GOLD', 'SNAPSHOT', 'MATERIALIZED VIEW']
            found_keywords = [kw for kw in keywords if kw in content]
            
            if found_keywords:
                print(f"    🎯 包含關鍵字: {', '.join(found_keywords)}")
        except Exception as e:
            print(f"    ❌ 讀取失敗: {e}")

def main():
    """診斷 Pipeline 缺失"""
    print("=" * 80)
    print("Pipeline 缺失原因診斷")
    print("=" * 80)
    
    # 1. 檢查 Gold 層表的建立方式
    sql_table_create = """
    SELECT 
        name,
        engine,
        create_table_query
    FROM system.tables 
    WHERE database = 'gold' 
      AND name = 'DAILY_L5_TASK_COMPLETION_SNAPSHOT'
    """
    
    results_create = query_clickhouse(sql_table_create, "Gold 層表建立方式")
    if results_create:
        for row in results_create:
            name, engine, query = row
            print(f"表名: {name}")
            print(f"引擎: {engine}")
            print(f"建立語句: {query[:200]}...")
    
    # 2. 檢查是否有 MATERIALIZED VIEW
    sql_mview = """
    SELECT 
        name,
        engine,
        create_table_query
    FROM system.tables 
    WHERE database IN ('gold', 'silver')
      AND (engine LIKE '%MaterializedView%' OR name LIKE '%SNAPSHOT%')
    """
    
    results_mview = query_clickhouse(sql_mview, "MATERIALIZED VIEW 檢查")
    if results_mview:
        print("發現的 Materialized Views:")
        for row in results_mview:
            name, engine, query = row
            print(f"\n📋 {name} ({engine}):")
            print(f"   {query[:300]}...")
    else:
        print("❌ 未發現任何 Materialized Views")
    
    # 3. 檢查是否有定時任務或 INSERT 語句
    sql_insert_log = """
    SELECT 
        event_time,
        query,
        user,
        query_duration_ms
    FROM system.query_log 
    WHERE query LIKE '%DAILY_L5_TASK_COMPLETION_SNAPSHOT%'
      AND type = 'QueryFinish'
      AND event_time >= now() - INTERVAL 7 DAY
    ORDER BY event_time DESC
    LIMIT 10
    """
    
    results_insert = query_clickhouse(sql_insert_log, "最近 7 天的 Gold 層操作記錄")
    if results_insert:
        print("最近的 Gold 層操作:")
        for row in results_insert:
            time, query, user, duration = row
            print(f"  {time} ({user}): {query[:100]}... ({duration}ms)")
    else:
        print("❌ 最近 7 天無 Gold 層操作記錄")
    
    # 4. 檢查 Silver 層資料是否正常
    sql_silver_recent = """
    SELECT 
        toDate(task_create_time) as date,
        COUNT(*) as count,
        COUNT(DISTINCT vx_type) as vx_types,
        COUNT(DISTINCT plant) as plants
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_time >= now() - INTERVAL 7 DAY
      AND is_excluded = 0
    GROUP BY toDate(task_create_time)
    ORDER BY date DESC
    """
    
    results_silver_recent = query_clickhouse(sql_silver_recent, "Silver 層最近 7 天資料")
    if results_silver_recent:
        print("Silver 層最近資料:")
        for row in results_silver_recent:
            date, count, vx_types, plants = row
            print(f"  {date}: {count}筆, {vx_types}種VX類型, {plants}個廠區")
    
    # 5. 檢查 Gold 層表結構
    sql_gold_structure = """
    SELECT 
        name,
        type,
        default_kind,
        comment
    FROM system.columns 
    WHERE database = 'gold' 
      AND table = 'DAILY_L5_TASK_COMPLETION_SNAPSHOT'
    ORDER BY position
    """
    
    results_structure = query_clickhouse(sql_gold_structure, "Gold 層表結構")
    if results_structure:
        print("Gold 層表欄位:")
        for row in results_structure:
            name, type_name, default_kind, comment = row
            print(f"  {name}: {type_name} ({default_kind}) - {comment}")
    
    # 6. 檢查是否有 cron job 或 scheduler
    print("\n🔍 檢查可能的排程機制")
    print("-" * 60)
    
    # 檢查 Python 腳本
    python_files = glob.glob("scripts/*.py", recursive=True)
    scheduler_files = []
    
    for file in python_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read().upper()
                
            if any(keyword in content for keyword in ['SCHEDULE', 'CRON', 'DAILY_L5_TASK_COMPLETION_SNAPSHOT', 'GOLD']):
                scheduler_files.append(file)
        except:
            pass
    
    if scheduler_files:
        print("可能相關的 Python 腳本:")
        for file in scheduler_files:
            print(f"  📄 {file}")
    else:
        print("❌ 未找到相關的排程腳本")
    
    # 7. 檢查 SQL 檔案
    check_sql_files()
    
    # 8. 檢查 Gold 層資料插入的可能來源
    sql_possible_source = """
    SELECT 
        'silver_to_gold_manual' as source_type,
        COUNT(*) as record_count
    FROM (
        SELECT 
            toDate(task_create_time) as snapshot_date,
            vx_type,
            plant,
            factory,
            line,
            'day' as time_period_type,
            COUNT(*) as total_task_qty,
            SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_qty,
            SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_qty,
            SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_qty
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE is_excluded = 0
          AND toDate(task_create_time) = '2025-12-28'
        GROUP BY toDate(task_create_time), vx_type, plant, factory, line
    ) as manual_calc
    """
    
    results_source = query_clickhouse(sql_source, "模擬 Gold 層資料來源")
    if results_source:
        for row in results_source:
            source_type, count = row
            print(f"模擬來源 {source_type}: {count} 筆記錄")
    
    # 9. 總結診斷
    print("\n" + "=" * 80)
    print("Pipeline 診斷總結")
    print("=" * 80)
    
    print("🎯 可能的問題原因:")
    print("1. ❌ 缺少自動化的 ETL 流程 (Silver → Gold)")
    print("2. ❌ MATERIALIZED VIEW 未設定或未觸發")
    print("3. ❌ 定時任務 (cron job) 未運行")
    print("4. ❌ 手動 INSERT 腳本未執行")
    
    print("\n💡 建議檢查:")
    print("1. 尋找 Silver → Gold 的 ETL 腳本")
    print("2. 檢查是否有 MATERIALIZED VIEW 需要手動刷新")
    print("3. 確認定時任務的設定和狀態")
    print("4. 檢查 Gold 層表的寫入權限")

if __name__ == "__main__":
    main()