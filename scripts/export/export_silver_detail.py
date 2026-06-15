"""
Silver 明細匯出腳本
輸出：exports/silver_detail/{vx}_{region}.xlsx
規則：
  - 資料來源：silver.mv_fact_task_vx FINAL，is_excluded=0
  - 日期範圍：START_DATE ~ END_DATE (環境變數可覆蓋)
  - 自動判斷：若任一 vx×region 組合超過 EXCEL_LIMIT，改為按月多 Sheet
用法：
  python export_silver_detail.py              # 全組合
  python export_silver_detail.py --test       # 只跑最小組合 (V2_CNW)
  python export_silver_detail.py --vx V3 --region CNE
"""
import os
import argparse
import logging
import time
from datetime import date
from clickhouse_driver import Client
import xlsxwriter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── 專案根目錄（從腳本位置推算，不寫死絕對路徑）──────
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..'))

# ── 環境變數設定 (同 sync_unified_odbc.py 模式) ──────
CH_HOST     = os.getenv('CLICKHOUSE_HOST',     'REDACTED_IP')
CH_PORT     = int(os.getenv('CLICKHOUSE_PORT', '9000'))
CH_USER     = os.getenv('CLICKHOUSE_USERNAME', 'default')
CH_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', 'REDACTED_PASSWORD')

START_DATE  = os.getenv('EXPORT_START_DATE',  '2025-10-01')
END_DATE    = os.getenv('EXPORT_END_DATE',     str(date.today()))
OUT_DIR     = os.getenv('EXPORT_OUT_DIR',      os.path.join(_PROJECT_ROOT, 'prd_audit'))
EXCEL_LIMIT = int(os.getenv('EXCEL_ROW_LIMIT', '1000000'))   # 保守上限，低於 Excel 硬限 104 萬

# ── 欄位定義 ─────────────────────────────────────────
COLUMNS = [
    'task_id',
    'proc_inst_id',
    'l4_process_id',
    'l4_process_name',
    'task_definition_key',
    'task_name',
    'task_start_time',
    'task_claim_time',
    'task_end_time',
    'task_start_date',
    'task_claim_date',
    'task_end_date',
    'task_create_date',
    'duration_min',
    'processing_time_min',
    'ui_time_field',
    'status_daily',
    'status_weekly',
    'status_monthly',
    'vx_type',
    'region',
    'plant',
    'factory',
    'line',
    'mo_number',
    'model_name',
    'delivery_area',
    'schedule_number',
    'sap_plant',
    'sap_product_group',
    'pallet',
    'transfer_no',
    'qblock_event_id',
    'defect_sn',
    'assignee_code',
    'assignee_name',
]

SELECT_COLS = ', '.join(COLUMNS)
HEADERS     = COLUMNS

# ── ClickHouse 工具函數 ───────────────────────────────
def get_client():
    return Client(host=CH_HOST, port=CH_PORT, user=CH_USER, password=CH_PASSWORD)

def base_where(vx, region):
    return (
        f"task_primary_date >= '{START_DATE}' AND task_primary_date <= '{END_DATE}'"
        f" AND is_excluded = 0"
        f" AND vx_type = '{vx}' AND region = '{region}'"
    )

def count_rows(ch, vx, region):
    r = ch.execute(f"SELECT count() FROM silver.mv_fact_task_vx FINAL WHERE {base_where(vx, region)}")
    return r[0][0]

def get_months(ch, vx, region):
    rows = ch.execute(f"""
        SELECT DISTINCT toYYYYMM(task_primary_date) AS ym
        FROM silver.mv_fact_task_vx FINAL
        WHERE {base_where(vx, region)}
        ORDER BY ym
    """)
    return [str(r[0]) for r in rows]

def fetch_rows(ch, vx, region, ym=None):
    extra = f" AND toYYYYMM(task_primary_date) = {ym}" if ym else ""
    return ch.execute(f"""
        SELECT {SELECT_COLS}
        FROM silver.mv_fact_task_vx FINAL
        WHERE {base_where(vx, region)} {extra}
        ORDER BY task_start_date, proc_inst_id
    """)

# ── Excel 工具函數 ────────────────────────────────────
def write_sheet(workbook, sheet_name, rows):
    ws = workbook.add_worksheet(sheet_name[:31])
    for col_i, h in enumerate(HEADERS):
        ws.write(0, col_i, h)
    for row_i, row in enumerate(rows, start=1):
        for col_i, val in enumerate(row):
            ws.write(row_i, col_i, str(val) if val is not None else '')
    ws.autofilter(0, 0, len(rows), len(HEADERS) - 1)
    ws.freeze_panes(1, 0)
    logger.info(f"  Sheet [{sheet_name}]: {len(rows):,} 筆")
    return len(rows)

# ── 匯出單一組合 ──────────────────────────────────────
def export_combo(ch, vx, region, idx=None, total_combos=None):
    label = f"{vx}_{region or 'unknown'}"
    fname = os.path.join(OUT_DIR, f"{label}.xlsx")

    prefix = f"[{idx}/{total_combos}]" if idx and total_combos else ""
    t0 = time.time()

    total = count_rows(ch, vx, region)
    logger.info(f"{prefix} ▶ {label}：{total:,} 筆 → {fname}")

    workbook = xlsxwriter.Workbook(fname, {'constant_memory': True})

    if total <= EXCEL_LIMIT:
        rows = fetch_rows(ch, vx, region)
        write_sheet(workbook, label, rows)
    else:
        logger.info(f"  超過 {EXCEL_LIMIT:,}，改為按月多 Sheet")
        for ym in get_months(ch, vx, region):
            rows = fetch_rows(ch, vx, region, ym)
            write_sheet(workbook, f"{ym[:4]}-{ym[4:]}", rows)

    workbook.close()
    elapsed = time.time() - t0
    logger.info(f"{prefix} ✓ {label} 完成，耗時 {elapsed:.1f}s → {fname}")

# ── 主程式 ────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='匯出 Silver 明細至 Excel')
    parser.add_argument('--test',   action='store_true', help='只跑最小組合 (V2_CNW) 驗證流程')
    parser.add_argument('--vx',     type=str, help='指定 vx_type (V1/V2/V3)')
    parser.add_argument('--region', type=str, help='指定 region (CNE/CNS/CNW)')
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    ch = get_client()

    logger.info(f"日期範圍：{START_DATE} ~ {END_DATE}")
    logger.info(f"輸出目錄：{OUT_DIR}")
    logger.info(f"Excel 上限：{EXCEL_LIMIT:,}")

    if args.test:
        logger.info("TEST MODE：只跑 V2_CNW")
        export_combo(ch, 'V2', 'CNW', idx=1, total_combos=1)
        return

    if args.vx and args.region:
        if bool(args.vx) != bool(args.region):
            parser.error("--vx 和 --region 必須同時指定")
        export_combo(ch, args.vx.upper(), args.region.upper(), idx=1, total_combos=1)
        return

    # 全組合
    combos = ch.execute(f"""
        SELECT DISTINCT vx_type, region
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_primary_date >= '{START_DATE}'
          AND task_primary_date <= '{END_DATE}'
          AND is_excluded = 0
        ORDER BY vx_type, region
    """)
    total_combos = len(combos)
    logger.info(f"共 {total_combos} 個組合，開始依序匯出...")

    t_all = time.time()
    done, failed = [], []

    for idx, (vx, region) in enumerate(combos, start=1):
        try:
            export_combo(ch, vx, region, idx=idx, total_combos=total_combos)
            done.append(f"{vx}_{region}")
        except Exception as e:
            label = f"{vx}_{region}"
            logger.error(f"[{idx}/{total_combos}] ✗ {label} 失敗：{e}")
            failed.append(label)

    total_elapsed = time.time() - t_all
    logger.info("=" * 50)
    logger.info(f"全部完成！共耗時 {total_elapsed:.1f}s")
    logger.info(f"  成功 {len(done)} 個：{', '.join(done)}")
    if failed:
        logger.warning(f"  失敗 {len(failed)} 個：{', '.join(failed)}")

if __name__ == '__main__':
    main()
