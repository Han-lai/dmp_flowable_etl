import subprocess
import re
import sys
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt

# ============================================================
# Connection Settings
# ============================================================

CH_HOST     = "10.146.206.76"
CH_PORT     = 9000
CH_USER     = "default"
CH_PASSWORD = "1qaz2wsx3edc"
CH_DATABASE = "gold"

TABLE = "gold.rmv_l5_task_completion_v2"

# ============================================================
# Benchmark Parameters
# ============================================================

CONCURRENCY_LEVELS = [10, 50, 100]

ITERATIONS = 1000
WARMUP_ITERATIONS = 50

RANDOMIZE = True

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "benchmark_results"
OUTPUT_DIR.mkdir(exist_ok=True)

QUERIES_FILE = OUTPUT_DIR / "queries.sql"

# ============================================================
# Query Conditions
# ============================================================

CONDITIONS = [
    {"label": "A", "vx_type": "V1", "region": "CNS", "plant": "DG3", "factory": "SMT", "line": "ST02"},
    {"label": "B", "vx_type": "V3", "region": "CNS", "plant": "DG3", "factory": "SMT", "line": "ST02"},
    {"label": "C", "vx_type": "V3", "region": "CNE", "plant": "WJ2", "factory": "NBU", "line": "E5"},
    {"label": "D", "vx_type": "V3", "region": "CNE", "plant": "WJ2", "factory": "NBU", "line": "E5"},
]

DATE_RANGES = [
    {"label": "Oct", "start": "2024-10-25", "end": "2024-10-31"},
    {"label": "Nov", "start": "2024-11-24", "end": "2024-11-30"},
    {"label": "Dec", "start": "2024-12-25", "end": "2024-12-31"},
    {"label": "Jan", "start": "2025-01-25", "end": "2025-01-31"},
]

# ============================================================
# Generate SQL Queries
# ============================================================

def generate_queries_sql():
    sql_lines = []

    for cond in CONDITIONS:
        for dr in DATE_RANGES:

            vx = cond['vx_type']
            reg = cond['region']
            pl = cond['plant']
            fac = cond['factory']
            ln = cond['line']
            tg_date = dr['end']

            sql = f"""
SELECT *
FROM {TABLE}
WHERE snapshot_date = toDate('{tg_date}')
AND region = '{reg}'
AND plant = '{pl}'
AND factory = '{fac}'
AND line = '{ln}'
AND vx_type = '{vx}';
"""

            sql_lines.append(sql.strip())

    with open(QUERIES_FILE, "w") as f:
        f.write("\n".join(sql_lines))

    print(f"Generated {len(sql_lines)} queries")

# ============================================================
# Run Benchmark
# ============================================================

def run_benchmark(concurrency, warmup=False):

    iterations = WARMUP_ITERATIONS if warmup else ITERATIONS

    cmd = [
        "clickhouse-benchmark",
        f"--host={CH_HOST}",
        f"--port={CH_PORT}",
        f"--user={CH_USER}",
        f"--password={CH_PASSWORD}",
        f"--database={CH_DATABASE}",
        f"--concurrency={concurrency}",
        f"--iterations={iterations}"
    ]

    if RANDOMIZE:
        cmd.append("--randomize")

    with open(QUERIES_FILE) as q:
        result = subprocess.run(
            cmd,
            stdin=q,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3600
        )

    output = result.stdout + result.stderr

    if not warmup:
        raw_log = OUTPUT_DIR / f"raw_{concurrency}_users.log"
        with open(raw_log, "w") as f:
            f.write(output)

    return output

# ============================================================
# Parse Benchmark Output
# ============================================================

def extract(patterns, text):
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return "N/A"

def parse_metrics(output, concurrency):

    qps = extract(
        [r"QPS:\s*([\d.]+)", r"Queries per second:\s*([\d.]+)"],
        output
    )

    lat_avg = extract([r"avg\s+([\d.]+)\s*ms"], output)
    lat_p95 = extract([r"95%\s+([\d.]+)\s*ms"], output)
    lat_p99 = extract([r"99%\s+([\d.]+)\s*ms"], output)

    return {
        "Concurrency": concurrency,
        "QPS": float(qps) if qps != "N/A" else 0,
        "AvgLatency": lat_avg,
        "P95": lat_p95,
        "P99": lat_p99
    }

# ============================================================
# Generate Markdown Report
# ============================================================

def generate_markdown_report(results):

    lines = []
    lines.append("# ClickHouse Benchmark Report\n")

    lines.append("| Concurrency | QPS | Avg Latency | P95 | P99 |")
    lines.append("|-------------|-----|-------------|-----|-----|")

    for r in results:
        lines.append(
            f"| {r['Concurrency']} | {r['QPS']} | {r['AvgLatency']} | {r['P95']} | {r['P99']} |"
        )

    report = OUTPUT_DIR / "summary_report.md"

    with open(report, "w") as f:
        f.write("\n".join(lines))

# ============================================================
# Generate Scaling Chart
# ============================================================

def generate_chart(results):

    x = [r["Concurrency"] for r in results]
    y = [r["QPS"] for r in results]

    plt.figure()

    plt.plot(x, y, marker="o")

    plt.xlabel("Concurrency")
    plt.ylabel("QPS")

    plt.title("ClickHouse Concurrency Scaling")

    plt.grid(True)

    plt.savefig(OUTPUT_DIR / "qps_scaling.png")

# ============================================================
# Main Flow
# ============================================================

def main():

    generate_queries_sql()

    print("Warmup benchmark...")
    run_benchmark(1, warmup=True)

    results = []

    for level in CONCURRENCY_LEVELS:

        print(f"Running benchmark for {level} users")

        raw = run_benchmark(level)

        metrics = parse_metrics(raw, level)

        results.append(metrics)

    generate_markdown_report(results)

    generate_chart(results)

    print("Benchmark completed")

if __name__ == "__main__":
    main()