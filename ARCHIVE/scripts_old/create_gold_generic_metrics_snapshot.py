#!/usr/bin/env python3
"""
========================================
Gold 層快照腳本 - 通用指標
========================================
從 Silver 層計算並寫入 Gold 層快照：
1. L5 任務執行完成率
2. 人員使用率

來源表：
- silver.FACT_TASK_VX_ATTRIBUTION
- silver.DIM_CONFIG_USER

目標表：
- gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
- gold.DAILY_USER_UTILIZATION_SNAPSHOT
"""

import clickhouse_connect
from datetime import datetime, timedelta
import logging
import argparse

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CH_CONFIG = {
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}


def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)


def get_iso_week(date):
    """取得 ISO 週次"""
    return date.isocalendar()[1]


def get_week_range(date):
    """取得該週的起迄日期（週一至週日）"""
    weekday = date.weekday()
    start = date - timedelta(days=weekday)
    end = start + timedelta(days=6)
    return start, end


# ============================================
# L5 任務執行完成率快照
# ============================================

def create_l5_task_completion_snapshot(client, snapshot_date):
    """建立 L5 任務執行完成率快照"""
    logger.info(f"建立 L5 任務執行完成率快照: {snapshot_date}")
    
    # 計算時間區間
    month_start = snapshot_date.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    current_week = get_iso_week(snapshot_date)
    week_start, week_end = get_week_range(snapshot_date)
    
    prev_week_start, prev_week_end = get_week_range(snapshot_date - timedelta(days=7))
    prev2_week_start, prev2_week_end = get_week_range(snapshot_date - timedelta(days=14))
    
    # 時間區間定義
    time_periods = [
        ('month', snapshot_date.strftime('%Y-%m'), month_start, month_end),
        ('week', f'W{current_week:02d}', week_start, week_end),
        ('week', f'W{current_week-1:02d}', prev_week_start, prev_week_end),
        ('week', f'W{current_week-2:02d}', prev2_week_start, prev2_week_end),
    ]
    
    # 加入最近 7 天
    for i in range(1, 8):
        day = snapshot_date - timedelta(days=i)
        time_periods.append(('day', day.strftime('%Y-%m-%d'), day, day))
    
    total_rows = 0
    
    for period_type, period_value, start_date, end_date in time_periods:
        sql = f"""
        INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
        SELECT
            toDate('{snapshot_date}') AS snapshot_date,
            vx_type,
            COALESCE(vx_subtype, '') AS vx_subtype,
            COALESCE(plant, '') AS plant,
            COALESCE(factory, '') AS factory,
            COALESCE(line, '') AS line,
            '{period_type}' AS time_period_type,
            '{period_value}' AS time_period_value,
            
            -- 任務數
            countIf(task_status IN ('TODO', 'DOING', 'DONE')) AS total_task_qty,
            countIf(task_status = 'TODO') AS todo_qty,
            countIf(task_status = 'DOING') AS doing_qty,
            countIf(task_status = 'DONE') AS done_qty,
            countIf(task_status IN ('DOING', 'DONE')) AS doing_done_qty,
            countIf(task_status IN ('TODO', 'DOING')) AS todo_doing_acc_qty,
            
            -- 百分比
            if(total_task_qty > 0, round(todo_qty * 100.0 / total_task_qty, 2), 0) AS todo_pct,
            if(total_task_qty > 0, round(doing_qty * 100.0 / total_task_qty, 2), 0) AS doing_pct,
            if(total_task_qty > 0, round(done_qty * 100.0 / total_task_qty, 2), 0) AS done_pct,
            if(total_task_qty > 0, round(doing_done_qty * 100.0 / total_task_qty, 2), 0) AS doing_done_pct,
            
            toUnixTimestamp64Milli(now64(3)) AS _version,
            now64(3) AS _snapshot_time
            
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE is_excluded = 0
          AND task_create_date BETWEEN toDate('{start_date}') AND toDate('{end_date}')
        GROUP BY vx_type, vx_subtype, plant, factory, line
        HAVING total_task_qty > 0
        """
        
        client.command(sql)
        
        # 計算寫入筆數
        count_sql = f"""
        SELECT count() FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
        WHERE snapshot_date = toDate('{snapshot_date}')
          AND time_period_type = '{period_type}'
          AND time_period_value = '{period_value}'
        """
        count = client.command(count_sql)
        total_rows += count
        logger.info(f"  {period_type}/{period_value}: {count} 筆")
    
    return total_rows


# ============================================
# 人員使用率快照
# ============================================

def create_user_utilization_snapshot(client, snapshot_date):
    """建立人員使用率快照"""
    logger.info(f"建立人員使用率快照: {snapshot_date}")
    
    # 計算時間區間
    month_start = snapshot_date.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    current_week = get_iso_week(snapshot_date)
    week_start, week_end = get_week_range(snapshot_date)
    
    prev_week_start, prev_week_end = get_week_range(snapshot_date - timedelta(days=7))
    prev2_week_start, prev2_week_end = get_week_range(snapshot_date - timedelta(days=14))
    
    # 時間區間定義
    time_periods = [
        ('month', snapshot_date.strftime('%Y-%m'), month_start, month_end),
        ('week', f'W{current_week:02d}', week_start, week_end),
        ('week', f'W{current_week-1:02d}', prev_week_start, prev_week_end),
        ('week', f'W{current_week-2:02d}', prev2_week_start, prev2_week_end),
    ]
    
    # 加入最近 7 天
    for i in range(1, 8):
        day = snapshot_date - timedelta(days=i)
        time_periods.append(('day', day.strftime('%Y-%m-%d'), day, day))
    
    total_rows = 0
    
    for period_type, period_value, start_date, end_date in time_periods:
        sql = f"""
        INSERT INTO gold.DAILY_USER_UTILIZATION_SNAPSHOT
        WITH 
        -- Config Users（從維度表取得）
        config_users AS (
            SELECT 
                vx_type,
                plant,
                factory,
                count(DISTINCT emp_code) AS config_user_count
            FROM silver.DIM_CONFIG_USER
            WHERE is_config_user = 1
            GROUP BY vx_type, plant, factory
        ),
        
        -- Active Users（從任務表取得，需存在於 Config Users，使用 INNER JOIN）
        active_users AS (
            SELECT 
                t.vx_type,
                t.plant,
                t.factory,
                count(DISTINCT t.task_assignee_name) AS active_user_count
            FROM silver.FACT_TASK_VX_ATTRIBUTION t
            INNER JOIN silver.DIM_CONFIG_USER c
                ON c.emp_name = t.task_assignee_name
               AND c.vx_type = t.vx_type
               AND c.is_config_user = 1
            WHERE t.is_excluded = 0
              AND t.task_status IN ('DONE', 'DOING')
              AND t.task_create_date BETWEEN toDate('{start_date}') AND toDate('{end_date}')
            GROUP BY t.vx_type, t.plant, t.factory
        )
        
        SELECT
            toDate('{snapshot_date}') AS snapshot_date,
            c.vx_type,
            c.plant,
            c.factory,
            '' AS line,
            '{period_type}' AS time_period_type,
            '{period_value}' AS time_period_value,
            
            COALESCE(a.active_user_count, 0) AS active_users,
            c.config_user_count AS config_users,
            
            if(c.config_user_count > 0, 
               round(COALESCE(a.active_user_count, 0) * 100.0 / c.config_user_count, 2), 
               0) AS utilization_rate,
            
            toUnixTimestamp64Milli(now64(3)) AS _version,
            now64(3) AS _snapshot_time
            
        FROM config_users c
        LEFT JOIN active_users a 
            ON c.vx_type = a.vx_type 
           AND c.plant = a.plant 
           AND c.factory = a.factory
        WHERE c.config_user_count > 0
        """
        
        client.command(sql)
        
        # 計算寫入筆數
        count_sql = f"""
        SELECT count() FROM gold.DAILY_USER_UTILIZATION_SNAPSHOT
        WHERE snapshot_date = toDate('{snapshot_date}')
          AND time_period_type = '{period_type}'
          AND time_period_value = '{period_value}'
        """
        count = client.command(count_sql)
        total_rows += count
        logger.info(f"  {period_type}/{period_value}: {count} 筆")
    
    return total_rows


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='Gold 層通用指標快照')
    parser.add_argument('--date', type=str, help='快照日期 (YYYY-MM-DD)，預設為今天')
    parser.add_argument('--init', action='store_true', help='初始化表結構')
    args = parser.parse_args()
    
    # 決定快照日期
    if args.date:
        snapshot_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    else:
        snapshot_date = datetime.now().date()
    
    logger.info("=" * 60)
    logger.info("Gold 層快照 - 通用指標")
    logger.info(f"快照日期: {snapshot_date}")
    logger.info("=" * 60)
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        if args.init:
            logger.info("初始化表結構...")
            # 執行 DDL（需要先手動執行 sql/09_create_gold_generic_metrics.sql）
            logger.info("請先執行 sql/09_create_gold_generic_metrics.sql")
            return
        
        # 建立 L5 任務執行完成率快照
        l5_rows = create_l5_task_completion_snapshot(client, snapshot_date)
        
        # 建立人員使用率快照
        util_rows = create_user_utilization_snapshot(client, snapshot_date)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info(f"快照完成！")
        logger.info(f"  L5 任務執行完成率: {l5_rows} 筆")
        logger.info(f"  人員使用率: {util_rows} 筆")
        logger.info(f"  總耗時: {elapsed:.2f} 秒")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"快照失敗: {e}")
        raise


if __name__ == "__main__":
    main()
