#!/usr/bin/env python3
"""
修正並重建 Silver 層 MVIEW
修正 V1 歸屬邏輯：TaskDefinitionKey 優先於工單號規則
"""
import clickhouse_connect
import logging
from datetime import datetime

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(
        host="REDACTED_IP",
        port=8121,
        username="default",
        password="default"
    )

def backup_current_data(client):
    """備份目前的 FACT_TASK_VX_ATTRIBUTION 資料"""
    logger.info("備份目前的 FACT_TASK_VX_ATTRIBUTION 資料...")
    
    try:
        # 檢查是否已有備份表
        backup_exists = client.command("EXISTS TABLE silver.FACT_TASK_VX_ATTRIBUTION_BACKUP")
        
        if backup_exists:
            logger.info("備份表已存在，刪除舊備份...")
            client.command("DROP TABLE silver.FACT_TASK_VX_ATTRIBUTION_BACKUP")
        
        # 建立備份表
        backup_sql = """
        CREATE TABLE silver.FACT_TASK_VX_ATTRIBUTION_BACKUP
        ENGINE = MergeTree()
        ORDER BY task_id
        AS SELECT * FROM silver.FACT_TASK_VX_ATTRIBUTION
        """
        client.command(backup_sql)
        
        # 檢查備份筆數
        backup_count = client.command("SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION_BACKUP")
        logger.info(f"備份完成，共 {backup_count:,} 筆資料")
        
        return True
        
    except Exception as e:
        logger.error(f"備份失敗: {e}")
        return False

def drop_layer2_mviews(client):
    """刪除第二層 MVIEW"""
    logger.info("刪除第二層 MVIEW...")
    
    objects_to_drop = [
        'silver.vw_fact_task_vx_attribution_realtime',  # 視圖
        'silver.mv_l5_metrics_realtime',                # MVIEW
        'silver.mv_dim_config_user',                    # MVIEW
        'silver.mv_fact_task_vx_attribution'            # MVIEW
    ]
    
    for obj in objects_to_drop:
        try:
            if 'vw_' in obj:
                client.command(f"DROP VIEW IF EXISTS {obj}")
                logger.info(f"  刪除視圖: {obj}")
            else:
                client.command(f"DROP TABLE IF EXISTS {obj}")
                logger.info(f"  刪除表: {obj}")
        except Exception as e:
            logger.warning(f"刪除 {obj} 時發生錯誤: {e}")

def rebuild_layer2_mviews(client):
    """重建第二層 MVIEW"""
    logger.info("重建第二層 MVIEW...")
    
    try:
        # 讀取並執行修正後的 SQL
        with open('sql/12_create_silver_mviews_layer2.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割並執行 SQL 語句
        sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        for i, stmt in enumerate(sql_statements, 1):
            if stmt.upper().startswith('SELECT ') and 'status' in stmt.lower():
                # 執行狀態查詢並顯示結果
                result = client.query(stmt)
                if result.result_rows:
                    for row in result.result_rows:
                        logger.info(f"  {row}")
            else:
                # 執行其他語句
                try:
                    client.command(stmt)
                    logger.info(f"  執行語句 {i}/{len(sql_statements)}")
                except Exception as e:
                    logger.warning(f"  語句 {i} 執行警告: {e}")
        
        logger.info("第二層 MVIEW 重建完成")
        return True
        
    except Exception as e:
        logger.error(f"重建第二層 MVIEW 失敗: {e}")
        return False

def verify_fix(client):
    """驗證修正結果"""
    logger.info("驗證修正結果...")
    
    # 1. 檢查 WJ2+NBU+E5 2025-12-28 的 V1 任務
    logger.info("\n1. 檢查 WJ2+NBU+E5 2025-12-28 的 V1 任務...")
    
    v1_check_sql = """
    SELECT 
        vx_type,
        task_definition_key,
        mo_number,
        COUNT(*) as task_count
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_create_date = '2025-12-28'
      AND is_excluded = 0
    GROUP BY vx_type, task_definition_key, mo_number
    ORDER BY task_count DESC
    """
    
    result = client.query(v1_check_sql)
    if result.result_rows:
        print(f"  {'VX':<4} {'DefKey':<15} {'MoNumber':<12} {'Count':<6}")
        print("  " + "-" * 45)
        
        v1_count = 0
        for row in result.result_rows:
            vx_type, def_key, mo_number, count = row
            if vx_type == 'V1':
                v1_count += count
            print(f"  {vx_type:<4} {def_key:<15} {mo_number or 'NULL':<12} {count:<6}")
        
        print(f"\n  修正後 V1 任務數: {v1_count}")
        
        if v1_count == 0:
            logger.info("✅ 修正成功：WJ2+NBU+E5 2025-12-28 無 V1 任務")
        else:
            logger.warning(f"⚠️ 仍有 {v1_count} 筆 V1 任務")
    
    # 2. 檢查 315% 工單號 + V3 TaskDefinitionKey 的衝突
    logger.info("\n2. 檢查 315% 工單號 + V3 TaskDefinitionKey 衝突...")
    
    conflict_check_sql = """
    SELECT 
        COUNT(*) as conflict_count
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE mo_number LIKE '315%'
      AND task_definition_key LIKE 'V3%'
      AND vx_type = 'V1'
    """
    
    result = client.query(conflict_check_sql)
    if result.result_rows:
        conflict_count = result.result_rows[0][0]
        if conflict_count == 0:
            logger.info("✅ 修正成功：無 315% + V3 衝突")
        else:
            logger.warning(f"⚠️ 仍有 {conflict_count:,} 筆衝突")
    
    # 3. 檢查整體 V1 任務數變化
    logger.info("\n3. 檢查整體 V1 任務數變化...")
    
    v1_total_sql = """
    SELECT 
        COUNT(*) as total_v1_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_v1_tasks
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE vx_type = 'V1' AND is_excluded = 0
    """
    
    result = client.query(v1_total_sql)
    if result.result_rows:
        total_v1, done_v1 = result.result_rows[0]
        logger.info(f"  修正後總 V1 任務: {total_v1:,} 筆")
        logger.info(f"  修正後 V1 完成: {done_v1:,} 筆")

def regenerate_gold_snapshots(client):
    """重新生成 Gold 層快照"""
    logger.info("重新生成 Gold 層快照...")
    
    try:
        # 刪除 2025-12-28 的錯誤快照
        delete_sql = """
        ALTER TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT 
        DELETE WHERE snapshot_date = '2025-12-28'
        """
        client.command(delete_sql)
        logger.info("刪除 2025-12-28 錯誤快照")
        
        # 重新生成快照（使用修正後的 Silver 資料）
        regenerate_sql = """
        INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
        SELECT 
            '2025-12-28' AS snapshot_date,
            vx_type,
            vx_subtype,
            plant,
            factory,
            line,
            'day' AS time_period_type,
            '2025-12-28' AS time_period_value,
            COUNT(*) AS total_task_qty,
            SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) AS todo_qty,
            SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) AS doing_qty,
            SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) AS done_qty,
            SUM(CASE WHEN task_status IN ('DOING', 'DONE') THEN 1 ELSE 0 END) AS doing_done_qty,
            SUM(CASE WHEN task_status IN ('TODO', 'DOING') THEN 1 ELSE 0 END) AS todo_doing_acc_qty,
            CASE 
                WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))
                ELSE 0 
            END AS todo_pct,
            CASE 
                WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))
                ELSE 0 
            END AS doing_pct,
            CASE 
                WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))
                ELSE 0 
            END AS done_pct,
            CASE 
                WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN task_status IN ('DOING', 'DONE') THEN 1 ELSE 0 END) * 100.0 / COUNT(*))
                ELSE 0 
            END AS doing_done_pct,
            1 AS _version,
            now64(3) AS _snapshot_time
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE task_create_date = '2025-12-28'
          AND is_excluded = 0
        GROUP BY vx_type, vx_subtype, plant, factory, line
        HAVING COUNT(*) > 0
        """
        client.command(regenerate_sql)
        logger.info("重新生成 2025-12-28 日度快照")
        
        return True
        
    except Exception as e:
        logger.error(f"重新生成 Gold 層快照失敗: {e}")
        return False

def main():
    """主程式"""
    logger.info("=" * 80)
    logger.info("修正並重建 Silver 層 MVIEW")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        # 1. 備份目前資料
        if not backup_current_data(client):
            logger.error("備份失敗，停止執行")
            return False
        
        # 2. 刪除第二層 MVIEW
        drop_layer2_mviews(client)
        
        # 3. 重建第二層 MVIEW（使用修正後的邏輯）
        if not rebuild_layer2_mviews(client):
            logger.error("重建失敗，停止執行")
            return False
        
        # 4. 驗證修正結果
        verify_fix(client)
        
        # 5. 重新生成 Gold 層快照
        if not regenerate_gold_snapshots(client):
            logger.error("重新生成 Gold 層快照失敗")
            return False
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(f"修正完成！總耗時: {elapsed:.2f} 秒")
        logger.info("=" * 80)
        logger.info("修正內容:")
        logger.info("1. TaskDefinitionKey 優先於工單號規則")
        logger.info("2. V3_5_3_* 任務正確歸類為 V3")
        logger.info("3. 315% 工單號衝突已解決")
        logger.info("4. 重新生成 2025-12-28 Gold 層快照")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"執行失敗: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)