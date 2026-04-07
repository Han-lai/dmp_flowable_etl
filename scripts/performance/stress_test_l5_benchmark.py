"""
stress_test_l5_benchmark.py
============================
使用 clickhouse-benchmark 官方工具對 L5 Gold Layer 執行多階段壓力測試。

功能：
  階段一：自動產生 queries.sql (4 條件組 × 4 月份 = 16 條 SQL)
  階段二：依序執行多階段併發測試 [10, 50, 100]
  階段三：產生每階段獨立報告與最終總結表格 (summary_report.txt)

使用方式：
  python stress_test_l5_benchmark.py

需求：
  - clickhouse-benchmark 需已安裝並在 PATH 中可執行
  - Python 3.8+，不需額外 Python 套件
"""

import subprocess
import re
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# =============================================================================
# 連線設定
# =============================================================================
CH_HOST     = "REDACTED_IP"
CH_PORT     = 9000           # clickhouse-benchmark 使用 Native TCP port
CH_USER     = "default"
CH_PASSWORD = "REDACTED_PASSWORD"
CH_DATABASE = "gold"

# 壓測參數 (包含 10, 50, 100 併發階梯)
CONCURRENCY_LEVELS = [10, 50, 100]
ITERATIONS         = 100            # 每階段總共執行 100 次查詢
RANDOMIZE          = 1              # 1 = 隨機抽取 SQL 執行

# 資料表名稱 (對接官方 Gold Layer 視圖)
TABLE = "gold.rmv_l5_task_completion"

# 輸出檔案路徑
SCRIPT_DIR   = Path(__file__).parent
QUERIES_FILE = SCRIPT_DIR / "queries.sql"
SUMMARY_FILE = SCRIPT_DIR / "summary_report.txt"

# =============================================================================
# 查詢條件池
# =============================================================================
CONDITIONS = [
    {"label": "A", "vx_type": "V1", "region": "CNS", "plant": "DG3", "factory": "SMT", "line": "ST02"},
    {"label": "B", "vx_type": "V3", "region": "CNS", "plant": "DG3", "factory": "SMT", "line": "ST02"},
    {"label": "C", "vx_type": "V3", "region": "CNE", "plant": "WJ2", "factory": "NBU", "line": "E5"},
    {"label": "D", "vx_type": "V3", "region": "CNE", "plant": "WJ2", "factory": "NBU", "line": "E5"},
]

DATE_RANGES = [
    {"label": "Oct",  "start": "2024-10-25", "end": "2024-10-31"},
    {"label": "Nov",  "start": "2024-11-24", "end": "2024-11-30"},
    {"label": "Dec",  "start": "2024-12-25", "end": "2024-12-31"},
    {"label": "Jan",  "start": "2025-01-25", "end": "2025-01-31"},
]


# =============================================================================
# 階段一：產生 queries.sql (保留原始邏輯)
# =============================================================================
def generate_queries_sql() -> int:
    """產生 16 條測試 SQL 寫入 queries.sql。"""
    print("=" * 60)
    print("[階段一] 產生 queries.sql")
    print("=" * 60)

    sql_lines = []
    for cond in CONDITIONS:
        for dr in DATE_RANGES:
            tg_date = dr['end']
            vx, reg, pl, fac, ln = cond['vx_type'], cond['region'], cond['plant'], cond['factory'], cond['line']

            sql = (
                f"WITH params AS (SELECT max(snapshot_date) as max_filtered_date, today() as sys_today FROM {TABLE} WHERE (snapshot_date = toDate('{tg_date}')) AND region = '{reg}' AND plant = '{pl}' AND factory = '{fac}' AND line = '{ln}' AND vx_type = '{vx}'), "
                f"calc_anchor AS (SELECT CASE WHEN max_filtered_date >= sys_today THEN sys_today ELSE max_filtered_date END as anchor_dt, sys_today FROM params), "
                f"base AS (SELECT * FROM {TABLE} CROSS JOIN calc_anchor WHERE snapshot_date >= toStartOfMonth(anchor_dt) - INTERVAL 1 MONTH AND snapshot_date <= toLastDayOfMonth(anchor_dt) + INTERVAL 1 MONTH AND region = '{reg}' AND plant = '{pl}' AND factory = '{fac}' AND line = '{ln}' AND vx_type = '{vx}') "
                f"SELECT 'Month' as granularity, formatDateTime(anchor_dt, '%b.') as period_name, 1 as sort_order, vx_type, region, plant, factory, line, anchor_dt as filter_date, anchor_dt as snapshot_date_real, sum(total_task) as total_qty, sum(todo_count) as todo_qty, sum(doing_count) as doing_qty, sum(doing_count + done_count) as doing_done_qty, sum(done_count) as done_qty, argMax(acc_todo_doing, snapshot_date) as acc_qty, sum(total_task) as acc_total_qty FROM base CROSS JOIN calc_anchor WHERE snapshot_date >= toStartOfMonth(anchor_dt) AND snapshot_date <= anchor_dt GROUP BY vx_type, region, plant, factory, line, anchor_dt, period_name "
                f"UNION ALL "
                f"SELECT 'Week' as granularity, concat('W', toString(toWeek(snapshot_date, 1))) as period_name, CASE WHEN toWeek(snapshot_date, 1) = toWeek(anchor_dt, 1) THEN 2 WHEN toWeek(snapshot_date, 1) = toWeek(anchor_dt - INTERVAL 7 DAY, 1) THEN 3 ELSE 4 END as sort_order, vx_type, region, plant, factory, line, anchor_dt as filter_date, max(snapshot_date) as snapshot_date_real, sum(total_task) as total_qty, sum(todo_count) as todo_qty, sum(doing_count) as doing_qty, sum(doing_count + done_count) as doing_done_qty, sum(done_count) as done_qty, argMax(acc_todo_doing, snapshot_date) as acc_qty, sum(total_task) as acc_total_qty FROM base CROSS JOIN calc_anchor WHERE ((toWeek(snapshot_date, 1) = toWeek(anchor_dt, 1) AND snapshot_date <= anchor_dt) OR (toWeek(snapshot_date, 1) = toWeek(anchor_dt - INTERVAL 7 DAY, 1)) OR (toWeek(snapshot_date, 1) = toWeek(anchor_dt - INTERVAL 14 DAY, 1))) GROUP BY granularity, period_name, sort_order, vx_type, region, plant, factory, line, anchor_dt "
                f"UNION ALL "
                f"SELECT granularity, period_name, sort_order, vx_type, region, plant, factory, line, filter_date, snapshot_date_real, total_qty, todo_qty, doing_qty, doing_done_qty, done_qty, acc_qty, sum(total_qty) OVER (PARTITION BY vx_type, region, plant, factory, line ORDER BY snapshot_date_real ASC ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as acc_total_qty FROM (SELECT 'Day' as granularity, toString(snapshot_date) as period_name, 5 + dateDiff('day', snapshot_date, anchor_dt) as sort_order, vx_type, region, plant, factory, line, anchor_dt as filter_date, snapshot_date as snapshot_date_real, total_task as total_qty, todo_count as todo_qty, doing_count as doing_qty, (doing_count + done_count) as doing_done_qty, done_count as done_qty, acc_todo_doing as acc_qty FROM base CROSS JOIN calc_anchor WHERE snapshot_date BETWEEN (anchor_dt - INTERVAL 13 DAY) AND anchor_dt) AS daily_stream WHERE snapshot_date_real BETWEEN (filter_date - INTERVAL 6 DAY) AND filter_date "
                f"UNION ALL "
                f"SELECT 'FilterRef' as granularity, '' as period_name, 99 as sort_order, '' as vx_type, '' as region, '' as plant, '' as factory, '' as line, snapshot_date as filter_date, snapshot_date as snapshot_date_real, 0 as total_qty, 0 as todo_qty, 0 as doing_qty, 0 as doing_done_qty, 0 as done_qty, 0 as acc_qty, 0 as acc_total_qty FROM (SELECT DISTINCT snapshot_date FROM {TABLE});"
            )
            sql_lines.append(sql)

    with open(QUERIES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines) + "\n")

    print(f"  → 已產生 {len(sql_lines)} 條 SQL 至: {QUERIES_FILE}")
    return len(sql_lines)


# =============================================================================
# 階段二：執行 clickhouse-benchmark (增加併發參數)
# =============================================================================
def run_benchmark(concurrency: int) -> str:
    """呼叫 clickhouse-benchmark 執行壓測，回傳原始輸出。"""
    print("-" * 40)
    print(f"[執行測試] 併發數: {concurrency} users")
    print("-" * 40)

    cmd = [
        "clickhouse-benchmark",
        f"--host={CH_HOST}",
        f"--port={CH_PORT}",
        f"--user={CH_USER}",
        f"--password={CH_PASSWORD}",
        f"--database={CH_DATABASE}",
        f"--concurrency={concurrency}",
        f"--iterations={ITERATIONS}"
    ]
    if RANDOMIZE:
        cmd.append("--randomize")

    try:
        with open(QUERIES_FILE, "r", encoding="utf-8") as query_input:
            result = subprocess.run(
                cmd, stdin=query_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600
            )

        output = result.stderr + result.stdout
        if result.returncode != 0:
            print(f"  [Error] 測試異常結束，退出碼: {result.returncode}")
        return output

    except FileNotFoundError:
        print("  [Error] 找不到 clickhouse-benchmark 指令！")
        sys.exit(1)


# =============================================================================
# 階段三：解析結果並產生報告 (增加回傳值)
# =============================================================================
def parse_and_report(raw_output: str, query_count: int, concurrency: int) -> Dict[str, str]:
    """解析測試數據，儲存單階段報告並回傳核心指標。"""
    
    def extract(pattern: str, text: str, default: str = "N/A") -> str:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else default

    # 擷取關鍵指標
    qps      = extract(r"QPS:\s*([\d.]+)", raw_output)
    lat_avg  = extract(r"avg\s+([\d.]+)\s*ms", raw_output)
    lat_p50  = extract(r"50%\s+([\d.]+)\s*ms", raw_output)
    lat_p95  = extract(r"95%\s+([\d.]+)\s*ms", raw_output)
    lat_p99  = extract(r"99%\s+([\d.]+)\s*ms", raw_output)

    # 某些版本的輸出格式容錯
    if lat_avg == "N/A": lat_avg = extract(r"Latency avg[:\s]+([\d.]+)", raw_output)
    if lat_p95 == "N/A": lat_p95 = extract(r"Latency\s+P95[:\s]+([\d.]+)", raw_output)

    report_path = SCRIPT_DIR / f"result_report_{concurrency}_users.txt"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 建立報告內容
    report_content = [
        "=" * 60,
        f"  ClickHouse L5 壓力測試報告 ({concurrency} Users)",
        f"  測試時間 : {now_str}",
        "=" * 60,
        "",
        "【測試設定】",
        f"  主機       : {CH_HOST}:{CH_PORT}",
        f"  併發數     : {concurrency} 人",
        f"  總執行次數 : {ITERATIONS} 次",
        "",
        "【效能指標】",
        f"  QPS                 : {qps}",
        f"  Avg Latency         : {lat_avg} ms",
        f"  Latency P50         : {lat_p50} ms",
        f"  Latency P95         : {lat_p95} ms",
        f"  Latency P99         : {lat_p99} ms",
        "",
        "=" * 60,
        "【原始輸出】",
        raw_output
    ]

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_content))
    
    print(f"  → 單階段報告已存儲: {report_path.name}")
    
    return {
        "Concurrency": str(concurrency),
        "QPS": qps,
        "Avg Latency": f"{lat_avg} ms",
        "P95": f"{lat_p95} ms",
        "P99": f"{lat_p99} ms"
    }


# =============================================================================
# 階段四：產生總結報告
# =============================================================================
def generate_summary_report(results: List[Dict[str, str]]) -> None:
    """彙整所有併發等級的結果為表格。"""
    print("\n" + "=" * 60)
    print("[階段四] 產生總結報告 summary_report.txt")
    print("=" * 60)

    header = f"{'Concurrency':<12} | {'QPS':<10} | {'Avg Latency':<12} | {'P95':<12} | {'P99':<12}"
    divider = "-" * len(header)
    
    table_lines = [header, divider]
    for r in results:
        line = f"{r['Concurrency']:<12} | {r['QPS']:<10} | {r['Avg Latency']:<12} | {r['P95']:<12} | {r['P99']:<12}"
        table_lines.append(line)

    summary_content = [
        "ClickHouse 多階段併發測試總結",
        f"測試日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"伺服器: {CH_HOST}",
        "",
        "\n".join(table_lines)
    ]

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_content))
    
    print("\n".join(table_lines))
    print(f"\n  → 總結報告已產生: {SUMMARY_FILE}")


# =============================================================================
# 主程式
# =============================================================================
def main():
    print("\n" + "!" * 60)
    print("  L5 ClickHouse Concurrency Scaling Test")
    print("!" * 60 + "\n")

    # 1. 產生 SQL
    query_count = generate_queries_sql()

    # 2. 迴圈測試各併發等級
    all_metrics = []
    for level in CONCURRENCY_LEVELS:
        raw_output = run_benchmark(level)
        metrics = parse_and_report(raw_output, query_count, level)
        all_metrics.append(metrics)

    # 3. 產生最終總結
    generate_summary_report(all_metrics)

    print("\n[完成] 所有併發階段壓測結束。")


if __name__ == "__main__":
    main()
