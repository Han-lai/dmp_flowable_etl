#!/usr/bin/env python3
"""
========================================
Parts 爆炸問題修正腳本
========================================
用途：修正 ClickHouse Parts 爆炸問題
執行：
1. 立即合併現有 parts
2. 調整 ClickHouse 設定
3. 驗證修正效果

使用方式：
- python scripts/fix_parts_explosion.py
"""

import clickhouse_connect
from datetime import datetime
import logging

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CH_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)

def check_parts_status(client):
    """檢查 Parts 狀態"""
    logger.info("檢查 Parts 狀態...")
    
    query = """
    SELECT 
        database,
        table,
        count() as parts_count,
        sum(rows) as total_rows,
        formatReadableSize(sum(bytes_on_disk)) as size_on_disk
    FROM system.parts 
    WHERE database = 'bronze' AND active = 1
    GROUP BY database, table
    HAVING parts_count > 1
    ORDER BY parts_count DESC
    """
    
    result = client.query(query)
    
    if not result.result_rows:
        logger.info("✅ 沒有發現 Parts 爆炸問題")
        return []
    
    problem_tables = []
    logger.info("🔍 發現以下表有 Parts 爆炸問題:")
    for row in result.result_rows:
        table_name = f"{row[0]}.{row[1]}"
        parts_count = row[2]
        total_rows = row[3]
        size = row[4]
        
        logger.info(f"  {table_name}: {parts_count} parts, {total_rows:,} rows, {size}")
        problem_tables.append(table_name)
    
    return problem_tables

def optimize_table(client, table_name):
    """優化單張表"""
    logger.info(f"🔧 優化表: {table_name}")
    
    try:
        # 執行 OPTIMIZE TABLE FINAL
        client.command(f"OPTIMIZE TABLE {table_name} FINAL")
        logger.info(f"✅ {table_name} 優化完成")
        return True
    except Exception as e:
        logger.error(f"❌ {table_name} 優化失敗: {e}")
        return False

def check_optimization_result(client, table_name):
    """檢查優化結果"""
    query = f"""
    SELECT 
        count() as parts_count,
        sum(rows) as total_rows
    FROM system.parts 
    WHERE database = splitByChar('.', '{table_name}')[1]
      AND table = splitByChar('.', '{table_name}')[2]
      AND active = 1
    """
    
    result = client.query(query)
    if result.result_rows:
        parts_count = result.result_rows[0][0]
        total_rows = result.result_rows[0][1]
        logger.info(f"  優化後: {table_name} = {parts_count} parts, {total_rows:,} rows")
        return parts_count
    return 0

def apply_clickhouse_settings(client):
    """應用 ClickHouse 設定優化"""
    logger.info("🔧 應用 ClickHouse 設定優化...")
    
    settings = [
        "SET max_insert_block_size = 1048576",  # 1M rows per block
        "SET parts_to_delay_insert = 150",      # 延遲插入閾值
        "SET parts_to_throw_insert = 300",      # 拒絕插入閾值
    ]
    
    for setting in settings:
        try:
            client.command(setting)
            logger.info(f"✅ 設定成功: {setting}")
        except Exception as e:
            logger.warning(f"⚠️ 設定失敗: {setting} - {e}")

def create_merge_settings_file():
    """建立 ClickHouse merge 設定檔案"""
    logger.info("📝 建立 ClickHouse merge 設定檔案...")
    
    settings_content = """<?xml version="1.0"?>
<clickhouse>
    <!-- Parts 管理設定 - 僅使用 ClickHouse 24.3 支援的參數 -->
    <merge_tree>
        <!-- Parts 控制設定 -->
        <parts_to_delay_insert>150</parts_to_delay_insert>
        <parts_to_throw_insert>300</parts_to_throw_insert>
        
        <!-- 插入批次大小設定 -->
        <max_insert_block_size>1048576</max_insert_block_size>
        <min_insert_block_size_rows>262144</min_insert_block_size_rows>
        <min_insert_block_size_bytes>268435456</min_insert_block_size_bytes>
    </merge_tree>
</clickhouse>
"""
    
    try:
        with open("docker/clickhouse/config/merge_settings.xml", "w", encoding="utf-8") as f:
            f.write(settings_content)
        logger.info("✅ 設定檔案已建立: docker/clickhouse/config/merge_settings.xml")
        logger.info("⚠️ 需要重啟 ClickHouse 容器以套用設定")
    except Exception as e:
        logger.error(f"❌ 建立設定檔案失敗: {e}")

def main():
    """主程式"""
    logger.info("=" * 60)
    logger.info("Parts 爆炸問題修正開始")
    logger.info("=" * 60)
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        # 1. 檢查 Parts 狀態
        problem_tables = check_parts_status(client)
        
        if not problem_tables:
            logger.info("🎉 沒有發現 Parts 問題，無需修正")
            return
        
        # 2. 應用 ClickHouse 設定
        apply_clickhouse_settings(client)
        
        # 3. 優化問題表
        logger.info(f"\n🔧 開始優化 {len(problem_tables)} 張表...")
        success_count = 0
        
        for table_name in problem_tables:
            if optimize_table(client, table_name):
                success_count += 1
                # 檢查優化結果
                check_optimization_result(client, table_name)
        
        # 4. 建立設定檔案
        create_merge_settings_file()
        
        # 5. 最終檢查
        logger.info("\n🔍 最終 Parts 狀態檢查:")
        final_problem_tables = check_parts_status(client)
        
        # 6. 總結
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("Parts 爆炸問題修正完成")
        logger.info("=" * 60)
        logger.info(f"處理表數: {len(problem_tables)}")
        logger.info(f"成功優化: {success_count}")
        logger.info(f"剩餘問題: {len(final_problem_tables)}")
        logger.info(f"總耗時: {elapsed:.2f} 秒")
        
        if len(final_problem_tables) == 0:
            logger.info("🎉 所有 Parts 問題已修正！")
        else:
            logger.warning("⚠️ 部分表仍有 Parts 問題，可能需要手動處理")
        
        logger.info("\n📋 後續步驟:")
        logger.info("1. 重啟 ClickHouse 容器以套用新設定: docker-compose restart clickhouse")
        logger.info("2. 監控後續同步的 Parts 數量")
        logger.info("3. 定期執行 OPTIMIZE TABLE 合併 parts")
        logger.info("4. 考慮調整同步腳本批次大小")
        
    except Exception as e:
        logger.error(f"修正過程發生錯誤: {e}")
        raise

if __name__ == "__main__":
    main()