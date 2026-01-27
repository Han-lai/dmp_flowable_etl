#!/usr/bin/env python3
"""
Gold Layer Daily Snapshot Script
每日指標快照腳本

用途：
- 從 Silver RMV 計算 7 個 Gold 指標
- 從 Silver 通用指標表計算 L5 任務執行完成率、人員使用率
- 寫入 gold.DAILY_METRICS_SNAPSHOT、gold.DAILY_BIZ_EVENT_SNAPSHOT
- 寫入 gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT、gold.DAILY_USER_UTILIZATION_SNAPSHOT
- 支援重跑（ReplacingMergeTree 自動去重）

排程：
- 每日 10:00 Asia/Taipei (= 02:00 UTC)
- cron: 0 2 * * * python scripts/create_gold_snapshot.py

使用方式：
- python scripts/create_gold_snapshot.py          # 執行今日快照
- python scripts/create_gold_snapshot.py --date 2026-01-12  # 指定日期
- python scripts/create_gold_snapshot.py --init   # 初始化表結構
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import clickhouse_connect

# ClickHouse 連線設定
CH_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
}


def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)


def init_tables(client):
    """初始化 Gold 表結構"""
    sql_file = Path(__file__).parent.parent / "sql" / "07_create_gold_snapshot.sql"
    
    if not sql_file.exists():
        print(f"❌ SQL 檔案不存在: {sql_file}")
        return False
    
    sql_content = sql_file.read_text(encoding="utf-8")
    
    # 移除註解行
    lines = []
    for line in sql_content.split('\n'):
        stripped = line.strip()
        if not stripped.startswith('--'):
            lines.append(line)
    sql_content = '\n'.join(lines)
    
    # 分割並執行每個語句
    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    
    for stmt in statements:
        if stmt:
            try:
                client.command(stmt)
                # 取得語句類型
                words = stmt.split()
                stmt_type = words[0].upper() if words else "UNKNOWN"
                if stmt_type in ("CREATE", "DROP"):
                    # 取得物件名稱
                    if "DATABASE" in stmt.upper():
                        obj_name = "DATABASE gold"
                    elif "TABLE" in stmt.upper():
                        # 找到 TABLE 後面的名稱
                        idx = stmt.upper().find("TABLE")
                        rest = stmt[idx+5:].strip()
                        if rest.upper().startswith("IF"):
                            rest = rest.split(None, 3)[-1] if len(rest.split()) > 3 else rest
                        obj_name = rest.split()[0] if rest.split() else "unknown"
                    else:
                        obj_name = "unknown"
                    print(f"✅ {stmt_type}: {obj_name}")
            except Exception as e:
                print(f"⚠️ 執行失敗: {stmt[:50]}... - {e}")
    
    print("\n✅ Gold 表結構初始化完成")
    return True


def create_metrics_snapshot(client, snapshot_date: str = None):
    """
    建立任務層 + 流程層每日快照
    
    Args:
        client: ClickHouse client
        snapshot_date: 快照日期 (YYYY-MM-DD)，預設為今天 (Asia/Taipei)
    """
    if snapshot_date is None:
        # 使用 Asia/Taipei 時區的今天
        snapshot_date = datetime.now().strftime("%Y-%m-%d")
    
    sql = f"""
    INSERT INTO gold.DAILY_METRICS_SNAPSHOT
    WITH 
    -- 任務層指標
    task_metrics AS (
        SELECT
            COALESCE(FACTORY, '') AS factory,
            COALESCE(PLANT, '') AS plant,
            COALESCE(PROC_DEF_NAME, '') AS proc_def_name,
            countIf(TASK_STATUS IN ('TODO', 'DOING')) AS in_progress_task_count,
            countIf(TASK_STATUS = 'TODO') AS todo_count,
            countIf(TASK_STATUS = 'DOING') AS doing_count,
            countIf(TASK_STATUS = 'DONE_AUTO') AS done_auto_count,
            countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')) AS done_total_count,
            sumIf(toUInt64(WORK_DURATION_SEC), TASK_STATUS = 'DONE' AND WORK_DURATION_SEC > 0) AS total_work_duration_sec,
            countIf(TASK_STATUS = 'DONE' AND WORK_DURATION_SEC > 0) AS done_count
        FROM silver.RMV_HI_PROC_TASK_NODE FINAL
        GROUP BY factory, plant, proc_def_name
    ),
    -- 流程層指標
    proc_metrics AS (
        SELECT
            COALESCE(FACTORY, '') AS factory,
            COALESCE(PLANT, '') AS plant,
            COALESCE(PROC_DEF_NAME, '') AS proc_def_name,
            countIf(PROC_STATE = 'DOING') AS in_progress_proc_count,
            countIf(PROC_STATE = 'DONE') AS completed_proc_count
        FROM silver.RMV_HI_PROCINST_NODE FINAL
        GROUP BY factory, plant, proc_def_name
    )
    SELECT
        toDate('{snapshot_date}') AS snapshot_date,
        now64(3, 'Asia/Taipei') AS snapshot_time,
        t.factory,
        t.plant,
        t.proc_def_name,
        t.in_progress_task_count,
        t.todo_count,
        t.doing_count,
        t.done_auto_count,
        t.done_total_count,
        t.total_work_duration_sec,
        t.done_count,
        COALESCE(p.in_progress_proc_count, 0) AS in_progress_proc_count,
        COALESCE(p.completed_proc_count, 0) AS completed_proc_count,
        toUnixTimestamp64Milli(now64(3, 'Asia/Taipei')) AS _version
    FROM task_metrics t
    LEFT JOIN proc_metrics p 
        ON t.factory = p.factory 
        AND t.plant = p.plant 
        AND t.proc_def_name = p.proc_def_name
    """
    
    client.command(sql)
    
    # 查詢寫入筆數
    count = client.command(f"""
        SELECT count() FROM gold.DAILY_METRICS_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
    """)
    
    print(f"✅ DAILY_METRICS_SNAPSHOT: {count} 筆 (日期: {snapshot_date})")
    return count


def create_biz_event_snapshot(client, snapshot_date: str = None):
    """
    建立業務事件層每日快照
    
    Args:
        client: ClickHouse client
        snapshot_date: 快照日期 (YYYY-MM-DD)，預設為今天 (Asia/Taipei)
    """
    if snapshot_date is None:
        snapshot_date = datetime.now().strftime("%Y-%m-%d")
    
    sql = f"""
    INSERT INTO gold.DAILY_BIZ_EVENT_SNAPSHOT
    SELECT
        toDate('{snapshot_date}') AS snapshot_date,
        now64(3, 'Asia/Taipei') AS snapshot_time,
        COALESCE(FIRST_PROC_DEF_NAME, '') AS first_proc_def_name,
        countIf(IS_IN_PROGRESS = 1) AS in_progress_event_count,
        countIf(IS_IN_PROGRESS = 0) AS completed_event_count,
        sumIf(toUInt64(TOTAL_DURATION_SEC), TOTAL_DURATION_SEC > 0) AS total_event_duration_sec,
        toUnixTimestamp64Milli(now64(3, 'Asia/Taipei')) AS _version
    FROM silver.RMV_HI_BIZ_EVENT_INFO FINAL
    GROUP BY first_proc_def_name
    """
    
    client.command(sql)
    
    # 查詢寫入筆數
    count = client.command(f"""
        SELECT count() FROM gold.DAILY_BIZ_EVENT_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
    """)
    
    print(f"✅ DAILY_BIZ_EVENT_SNAPSHOT: {count} 筆 (日期: {snapshot_date})")
    return count


def create_l5_task_completion_snapshot(client, snapshot_date: str = None):
    """
    建立 L5 任務執行完成率每日快照
    
    使用 FlowableTaskStats 的 TaskStatus 欄位計算狀態
    
    Args:
        client: ClickHouse client
        snapshot_date: 快照日期 (YYYY-MM-DD)，預設為今天 (Asia/Taipei)
    """
    if snapshot_date is None:
        snapshot_date = datetime.now().strftime("%Y-%m-%d")
    
    sql = f"""
    INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    SELECT
        toDate('{snapshot_date}') AS snapshot_date,
        vx_type,
        COALESCE(vx_subtype, '') AS vx_subtype,
        COALESCE(plant, '') AS plant,
        COALESCE(factory, '') AS factory,
        COALESCE(line, '') AS line,
        'day' AS time_period_type,
        '{snapshot_date}' AS time_period_value,
        
        count() AS total_task_qty,
        countIf(task_status = 'TODO') AS todo_qty,
        countIf(task_status = 'DOING') AS doing_qty,
        countIf(task_status = 'DONE') AS done_qty,
        countIf(task_status IN ('DOING', 'DONE')) AS doing_done_qty,
        countIf(task_status IN ('TODO', 'DOING')) AS todo_doing_acc_qty,
        
        if(count() > 0, round(countIf(task_status = 'TODO') * 100.0 / count(), 2), 0) AS todo_pct,
        if(count() > 0, round(countIf(task_status = 'DOING') * 100.0 / count(), 2), 0) AS doing_pct,
        if(count() > 0, round(countIf(task_status = 'DONE') * 100.0 / count(), 2), 0) AS done_pct,
        if(count() > 0, round(countIf(task_status IN ('DOING', 'DONE')) * 100.0 / count(), 2), 0) AS doing_done_pct,
        
        toUnixTimestamp64Milli(now64(3)) AS _version,
        now64(3) AS _snapshot_time
        
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE is_excluded = 0
      AND task_create_date = toDate('{snapshot_date}')
    GROUP BY vx_type, vx_subtype, plant, factory, line
    HAVING total_task_qty > 0
    """
    
    client.command(sql)
    
    count = client.command(f"""
        SELECT count() FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
    """)
    
    print(f"✅ DAILY_L5_TASK_COMPLETION_SNAPSHOT: {count} 筆 (日期: {snapshot_date})")
    return count


def create_user_utilization_snapshot(client, snapshot_date: str = None):
    """
    建立人員使用率每日快照
    
    Args:
        client: ClickHouse client
        snapshot_date: 快照日期 (YYYY-MM-DD)，預設為今天 (Asia/Taipei)
    """
    if snapshot_date is None:
        snapshot_date = datetime.now().strftime("%Y-%m-%d")
    
    sql = f"""
    INSERT INTO gold.DAILY_USER_UTILIZATION_SNAPSHOT
    WITH 
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
    active_users AS (
        SELECT 
            t.vx_type,
            t.plant,
            t.factory,
            count(DISTINCT t.task_assignee_name) AS active_user_count
        FROM silver.FACT_TASK_VX_ATTRIBUTION t
        INNER JOIN silver.DIM_CONFIG_USER cu
            ON cu.emp_name = t.task_assignee_name
           AND cu.vx_type = t.vx_type
           AND cu.is_config_user = 1
        WHERE t.is_excluded = 0
          AND t.task_status IN ('DONE', 'DOING')
          AND t.task_create_date = toDate('{snapshot_date}')
        GROUP BY t.vx_type, t.plant, t.factory
    )
    SELECT
        toDate('{snapshot_date}') AS snapshot_date,
        c.vx_type,
        c.plant,
        c.factory,
        '' AS line,
        'day' AS time_period_type,
        '{snapshot_date}' AS time_period_value,
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
    
    count = client.command(f"""
        SELECT count() FROM gold.DAILY_USER_UTILIZATION_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
    """)
    
    print(f"✅ DAILY_USER_UTILIZATION_SNAPSHOT: {count} 筆 (日期: {snapshot_date})")
    return count


def show_snapshot_summary(client, snapshot_date: str = None):
    """顯示快照摘要"""
    if snapshot_date is None:
        snapshot_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n📊 快照摘要 ({snapshot_date})")
    print("=" * 60)
    
    # 任務層摘要
    result = client.query(f"""
        SELECT
            sum(in_progress_task_count) AS total_in_progress,
            sum(done_auto_count) AS total_done_auto,
            sum(done_total_count) AS total_done,
            sum(in_progress_proc_count) AS total_in_progress_proc,
            sum(completed_proc_count) AS total_completed_proc
        FROM gold.DAILY_METRICS_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
    """)
    
    if result.result_rows:
        row = result.result_rows[0]
        print(f"在途任務數: {row[0]:,}")
        print(f"自動完成數: {row[1]:,}")
        print(f"已完成總數: {row[2]:,}")
        if row[2] > 0:
            print(f"自動完成率: {row[1] * 100.0 / row[2]:.2f}%")
        print(f"在途流程數: {row[3]:,}")
        print(f"已完成流程數: {row[4]:,}")
    
    # 業務事件摘要
    result = client.query(f"""
        SELECT
            sum(in_progress_event_count) AS total_in_progress,
            sum(completed_event_count) AS total_completed,
            sum(total_event_duration_sec) AS total_duration
        FROM gold.DAILY_BIZ_EVENT_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
    """)
    
    if result.result_rows:
        row = result.result_rows[0]
        print(f"在途業務事件數: {row[0]:,}")
        print(f"已完成業務事件數: {row[1]:,}")
        if row[1] > 0:
            avg_duration = row[2] / row[1]
            print(f"平均業務事件歷時: {avg_duration / 3600:.2f} 小時")
    
    # L5 任務執行完成率摘要
    result = client.query(f"""
        SELECT
            vx_type,
            sum(total_task_qty) AS total,
            sum(done_qty) AS done,
            round(sum(done_qty) * 100.0 / sum(total_task_qty), 2) AS done_pct
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
        GROUP BY vx_type
        ORDER BY vx_type
    """)
    
    if result.result_rows:
        print(f"\nL5 任務執行完成率:")
        for row in result.result_rows:
            print(f"  {row[0]}: {row[2]:,}/{row[1]:,} ({row[3]}%)")
    
    # 人員使用率摘要
    result = client.query(f"""
        SELECT
            vx_type,
            sum(active_users) AS active,
            sum(config_users) AS config,
            round(sum(active_users) * 100.0 / sum(config_users), 2) AS rate
        FROM gold.DAILY_USER_UTILIZATION_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
        GROUP BY vx_type
        ORDER BY vx_type
    """)
    
    if result.result_rows:
        print(f"\n人員使用率:")
        for row in result.result_rows:
            print(f"  {row[0]}: {row[1]:,}/{row[2]:,} ({row[3]}%)")


def main():
    parser = argparse.ArgumentParser(description="Gold Layer Daily Snapshot")
    parser.add_argument("--date", help="快照日期 (YYYY-MM-DD)，預設為今天")
    parser.add_argument("--init", action="store_true", help="初始化表結構")
    args = parser.parse_args()
    
    client = get_client()
    
    if args.init:
        init_tables(client)
        return
    
    snapshot_date = args.date
    
    print(f"開始建立 Gold 快照...")
    print(f"   日期: {snapshot_date or '今天'}")
    print(f"   時區: Asia/Taipei")
    print()
    
    try:
        # 建立任務層 + 流程層快照
        create_metrics_snapshot(client, snapshot_date)
        
        # 建立業務事件層快照
        create_biz_event_snapshot(client, snapshot_date)
        
        # 建立 L5 任務執行完成率快照
        create_l5_task_completion_snapshot(client, snapshot_date)
        
        # 建立人員使用率快照
        create_user_utilization_snapshot(client, snapshot_date)
        
        # 顯示摘要
        show_snapshot_summary(client, snapshot_date)
        
        print("\n完成 Gold 快照建立完成")
        
    except Exception as e:
        print(f"\n錯誤 快照建立失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
