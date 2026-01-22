#!/usr/bin/env python3
"""
執行 MVIEW 時間邏輯修正
"""

import clickhouse_connect
import logging

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )

def execute_fix():
    """執行修正"""
    client = get_client()
    
    try:
        # 1. 先備份現有 MVIEW（如果存在）
        logger.info("備份現有 MVIEW...")
        try:
            client.command("CREATE TABLE silver.mv_l5_metrics_realtime_backup AS SELECT * FROM silver.mv_l5_metrics_realtime")
            logger.info("✅ 備份完成")
        except Exception as e:
            logger.warning(f"備份失敗（可能表不存在）: {e}")
        
        # 2. 刪除現有 MVIEW
        logger.info("刪除現有 MVIEW...")
        client.command("DROP TABLE IF EXISTS silver.mv_l5_metrics_realtime")
        logger.info("✅ 刪除完成")
        
        # 3. 重新建立符合規範的 MVIEW
        logger.info("建立修正後的 MVIEW...")
        
        create_mview_sql = """
        CREATE MATERIALIZED VIEW silver.mv_l5_metrics_realtime
        ENGINE = SummingMergeTree()
        ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line)
        SETTINGS allow_nullable_key = 1
        POPULATE
        AS
        WITH task_dates AS (
            SELECT 
                task_id,
                vx_type,
                vx_subtype,
                plant,
                factory,
                line,
                task_status,
                is_excluded,
                exclude_reason,
                is_special_v1_rule,
                _mview_update_time,
                
                -- 使用 OR 條件的時間邏輯：任務在任一時間點的日期都會被包含
                arrayDistinct(arrayFilter(x -> x IS NOT NULL, [
                    toDate(task_create_time),
                    toDate(task_claim_time),
                    toDate(task_end_time)
                ])) AS active_dates
                
            FROM silver.mv_fact_task_vx_attribution
            WHERE task_create_time IS NOT NULL
        ),
        
        -- 展開每個任務的所有活動日期
        task_date_expanded AS (
            SELECT 
                task_id,
                vx_type,
                vx_subtype,
                plant,
                factory,
                line,
                task_status,
                is_excluded,
                exclude_reason,
                is_special_v1_rule,
                _mview_update_time,
                arrayJoin(active_dates) AS snapshot_date
                
            FROM task_dates
            WHERE length(active_dates) > 0
        )
        
        SELECT
            snapshot_date,
            vx_type,
            vx_subtype,
            plant,
            factory,
            line,
            
            -- 基礎統計（只計算未排除的任務）
            countIf(is_excluded = 0) AS total_task_qty,
            countIf(is_excluded = 0 AND task_status = 'TODO') AS todo_qty,
            countIf(is_excluded = 0 AND task_status = 'DOING') AS doing_qty,
            countIf(is_excluded = 0 AND task_status = 'DONE') AS done_qty,
            
            -- 排除統計
            countIf(is_excluded = 1) AS excluded_qty,
            countIf(exclude_reason = 'bypass') AS bypass_qty,
            countIf(exclude_reason = 'E_prefix') AS e_prefix_qty,
            countIf(exclude_reason = 'C_prefix') AS c_prefix_qty,
            countIf(exclude_reason = 'Q_order') AS q_order_qty,
            countIf(exclude_reason = 'R_order') AS r_order_qty,
            
            -- V1 特殊規則統計
            countIf(is_special_v1_rule = 1) AS special_v1_rule_qty,
            
            now64(3) AS _mview_update_time
            
        FROM task_date_expanded
        GROUP BY 
            snapshot_date,
            vx_type,
            vx_subtype,
            plant,
            factory,
            line
        """
        
        client.command(create_mview_sql)
        logger.info("✅ 新 MVIEW 建立完成")
        
        # 4. 重新建立 Gold 層 MVIEW
        logger.info("重新建立 Gold 層 MVIEW...")
        client.command("DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
        
        create_gold_mview_sql = """
        CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
        ENGINE = ReplacingMergeTree()
        ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
        SETTINGS allow_nullable_key = 1
        POPULATE
        AS
        SELECT 
            snapshot_date,
            COALESCE(plant, '') AS plant,
            COALESCE(factory, '') AS factory,
            COALESCE(line, '') AS line,
            vx_type,
            COALESCE(vx_subtype, '') AS vx_subtype,
            
            -- 任務數量統計
            SUM(todo_qty) AS sum_todo_qty,
            SUM(doing_qty) AS sum_doing_qty,
            SUM(done_qty) AS sum_done_qty,
            SUM(total_task_qty) AS sum_total_task_qty,
            SUM(excluded_qty) AS sum_excluded_qty,
            
            -- 排除原因統計
            SUM(bypass_qty) AS sum_bypass_qty,
            SUM(e_prefix_qty) AS sum_e_prefix_qty,
            SUM(c_prefix_qty) AS sum_c_prefix_qty,
            SUM(q_order_qty) AS sum_q_order_qty,
            SUM(r_order_qty) AS sum_r_order_qty,
            
            -- 特殊規則統計
            SUM(special_v1_rule_qty) AS sum_special_v1_rule_qty,
            
            -- 完成率計算
            CASE 
                WHEN SUM(total_task_qty) > 0 
                THEN ROUND(SUM(done_qty) * 100.0 / SUM(total_task_qty), 2)
                ELSE 0.0
            END AS completion_rate,
            
            -- 進行中率計算
            CASE 
                WHEN SUM(total_task_qty) > 0 
                THEN ROUND((SUM(doing_qty) + SUM(done_qty)) * 100.0 / SUM(total_task_qty), 2)
                ELSE 0.0
            END AS progress_rate,
            
            now64(3) AS _mview_update_time
            
        FROM silver.mv_l5_metrics_realtime
        GROUP BY 
            snapshot_date,
            plant,
            factory,
            line,
            vx_type,
            vx_subtype
        """
        
        client.command(create_gold_mview_sql)
        logger.info("✅ Gold 層 MVIEW 建立完成")
        
        # 5. 檢查結果
        logger.info("檢查修正結果...")
        
        # 檢查新 MVIEW 的記錄數
        result = client.query("SELECT COUNT(*) as count FROM silver.mv_l5_metrics_realtime")
        new_count = result.result_rows[0][0]
        logger.info(f"新 MVIEW 記錄數: {new_count:,}")
        
        # 檢查備份的記錄數（如果存在）
        try:
            result = client.query("SELECT COUNT(*) as count FROM silver.mv_l5_metrics_realtime_backup")
            old_count = result.result_rows[0][0]
            logger.info(f"原 MVIEW 記錄數: {old_count:,}")
            logger.info(f"記錄數變化: {new_count - old_count:+,} ({((new_count - old_count) / old_count * 100):+.1f}%)")
        except:
            logger.info("無法比較原記錄數（備份不存在）")
        
        # 檢查特定日期的任務數量
        result = client.query("""
            SELECT 
                SUM(total_task_qty) AS total_tasks,
                SUM(todo_qty) AS todo_tasks,
                SUM(doing_qty) AS doing_tasks,
                SUM(done_qty) AS done_tasks
            FROM silver.mv_l5_metrics_realtime
            WHERE snapshot_date = '2025-12-30'
        """)
        
        if result.result_rows:
            total, todo, doing, done = result.result_rows[0]
            logger.info(f"2025-12-30 任務統計: 總計={total}, TODO={todo}, DOING={doing}, DONE={done}")
        
        logger.info("🎉 MVIEW 時間邏輯修正完成！")
        
    except Exception as e:
        logger.error(f"❌ 修正失敗: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    execute_fix()