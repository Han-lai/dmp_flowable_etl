#!/usr/bin/env python3
"""
每日同步對帳報表：比對 MSSQL 來源端與 ClickHouse bronze 的筆數，輸出可直接用 Excel 開啟的報表。

用途：每日排程跑完後，回答「相同條件下 MSSQL 有幾筆、ClickHouse 拉回幾筆、完成度多少」。

    python scripts/etl/tools/audit_sync_progress.py --csv report.csv

--------------------------------------------------------------------------------
四個設計重點（皆為實測驗證後的結論，改動前請先讀）
--------------------------------------------------------------------------------
1. cutoff 凍結
   排程執行期間 MSSQL 仍持續進資料，直接比整表筆數永遠對不齊。故兩邊一律套用同一個時間
   上界 cutoff（預設取該表 watermark 的 max_data_time），cutoff 之後的新資料算下一輪。

2. ClickHouse 端必須用 uniqExact(排序鍵)，不能用 count()
   bronze 全是 ReplacingMergeTree，重跑重疊區間會留下尚未合併的重複列（實測 taskinst /
   procinst 的原始筆數曾達來源的 2 倍）。用 count() 會算出超過 100%。

3. 排序鍵非唯一的表，兩邊都要用「同鍵去重後」的筆數
   NON_UNIQUE_KEY_TABLES 這四張表的排序鍵在來源端並不唯一，Replacing 會依鍵折疊掉語意
   不同的列（實測折疊 10%~99.5%）。這是既定行為不是同步缺口——四張表在鍵層級都是 100%、
   0 筆缺漏。故來源端也按同一組鍵去重再比，否則報表會把正常狀態誤報成大量漏同步。

4. 完成度之外必須同時看新鮮度（lag）
   cutoff 取自 watermark，若同步整個卡住，watermark 不前進、cutoff 也不前進，完成度會
   一路回報 100% 而看不出資料早已停滯。故另外量 max(MSSQL) - max(CH)。
"""

import argparse
import csv
import logging
import os
import sys
import time
import unicodedata
from pathlib import Path

# 共用 sync 腳本的連線與設定載入邏輯，避免 source/target/time_col 在兩處重複定義
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sync_unified_odbc import (  # noqa: E402
    build_odbc_conn,
    get_client,
    load_configs,
    mask_secrets,
    parse_source,
)

logger = logging.getLogger("audit_sync")

# Windows 主控台預設 cp950，中文 log 會變亂碼（排程 log 尤其難讀）
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ODBC_SETTINGS = "SETTINGS max_execution_time = 1800"

# 排序鍵在來源端非唯一的表：列數天生低於來源，改判「鍵層級完整度」，落差不視為缺口。
NON_UNIQUE_KEY_TABLES = {
    "varinst": "排序鍵缺 TASK_ID_，同流程同名同時間的任務層級變數會被折疊",
    "identitylink": "participant 類 TASK_ID_ 為空，同一人所有流程擠同一桶",
    "mdm_line_desc": "來源同一 (PROD_AREA_ID, LINE_NAME) 有多列",
    "kpi_user_config_log": "來源是按 ConfigDate 的歷史 log，排序鍵不含日期，只留每組最後一筆",
}

# 報表分類；順序即報表列出順序，未列到的表歸「其他」排在最後
TABLE_CATEGORIES = [
    ("人員/組織", ["hr_employee", "emp_node_role", "emp_org_info",
                   "emp_user_group", "user_group", "process_role_user"]),
    ("主檔(MDM)", ["mdm_line_desc", "mdm_prod_area", "mdm_factory_area",
                   "mdm_mfg_site", "mdm_mfg_plant"]),
    ("功能設定", ["dmp_func_config", "dmp_func_client_mapping"]),
    ("流程引擎(BPM)", ["procdef", "taskinst", "varinst", "procinst", "identitylink"]),
    ("人員每日匯總", ["kpi_user_config_log"]),
]

MAX_MISSING_KEYS_LISTED = 20


def parse_args():
    parser = argparse.ArgumentParser(
        description="每日 MSSQL → ClickHouse 同步對帳報表（輸出 Excel 可開的 CSV）"
    )
    parser.add_argument("--csv", metavar="PATH", help="輸出 CSV 路徑（UTF-8-BOM，Excel 可直接開）")
    parser.add_argument("--table", help="只對帳單一表（預設全部）")
    parser.add_argument("--config", default="sync_tables.yaml", help="config 目錄下的 YAML 檔名")
    parser.add_argument("--window-days", type=int, default=2,
                        help="batch 表的回看天數（自 cutoff 往前）。full 表一律比整表。預設 2")
    parser.add_argument("--cutoff", default="watermark",
                        help="時間上界：'watermark'(預設)、'now'、或 'YYYY-MM-DD HH:MM:SS'")
    parser.add_argument("--tolerance-pct", type=float, default=0.01,
                        help="容忍的落差百分比，用於吸收 cutoff 邊界效應。預設 0.01")
    parser.add_argument("--stale-hours", type=float, default=26.0,
                        help="落後超過幾小時判定資料停滯。預設 26（容忍一次排程失敗）")
    parser.add_argument("--strict", action="store_true",
                        help="有表未達 100%% 或資料停滯時以 exit 1 結束（供排程告警用）")
    return parser.parse_args()


# ---------------------------------------------------------------- 查詢輔助

def get_sorting_key(client, target):
    """自 system.tables 取排序鍵，避免在本工具再抄一份主鍵定義。"""
    db, tbl = target.split(".")
    return client.command(
        f"SELECT sorting_key FROM system.tables WHERE database = '{db}' AND name = '{tbl}'"
    )


def resolve_cutoff(client, target, mode):
    """決定凍結的時間上界。watermark 取不到時退回 now()。"""
    if mode == "now":
        return client.command("SELECT toString(now())")
    if mode != "watermark":
        return mode
    db = target.split(".")[0]
    # toDateTime 去掉毫秒：帶 .000 的字串無法被 toDateTime() 解析（CANNOT_PARSE_TEXT）
    return client.command(
        f"SELECT toString(toDateTime(ifNull(maxOrNull(max_data_time), now()))) "
        f"FROM {db}._sync_watermark FINAL WHERE table_name = '{target}'"
    )


def build_odbc_proxy(client, table_key, cfg):
    """建立顯式型別的 ODBC 代理表；沿用 sync 腳本的 DDL 以確保欄位型別一致。"""
    src = parse_source(cfg["source"])
    proxy = f"audit_odbc_{table_key}"
    client.command(f"DROP TABLE IF EXISTS {proxy}")
    client.command(
        f"CREATE TABLE {proxy} ({cfg['engine_ddl']}) "
        f"ENGINE = ODBC('{build_odbc_conn(src['db'])}', '{src['schema']}', '{src['table']}')"
    )
    return proxy


def sort_key_available(sort_key, engine_ddl):
    """排序鍵欄位必須都在 ODBC 代理表的欄位清單裡，否則無法在來源端做同鍵去重。"""
    ddl_cols = {
        part.strip().split()[0].strip("`")
        for part in engine_ddl.split(",") if part.strip()
    }
    return all(col.strip() in ddl_cols for col in sort_key.split(","))


def measure_lag(client, proxy, target, time_col):
    """量 CH 落後 MSSQL 多少秒（兩邊 max(time_col) 相減）。max() 在 ODBC 端有 pushdown。"""
    if not time_col:
        return None, None, None
    ch_max = client.command(f"SELECT toString(toDateTime(max({time_col}))) FROM {target}")
    src_max = client.command(
        f"SELECT toString(toDateTime(max({time_col}))) FROM {proxy} {ODBC_SETTINGS}")
    lag = int(client.command(
        f"SELECT toString(dateDiff('second', toDateTime('{ch_max}'), toDateTime('{src_max}')))"))
    return ch_max, src_max, lag


def find_missing_keys(client, proxy, target, sort_key, where, time_col):
    """
    列出來源端有、CH 端沒有的排序鍵——也就是「未同步筆數」到底缺了哪幾筆。

    只在確實有落差時才呼叫（NOT IN 子查詢很貴），正常狀態下不會付這個成本。
    """
    cols = [c.strip() for c in sort_key.split(",")]
    sel = ", ".join(cols)
    order = f"min({time_col}) AS first_seen" if time_col else "count() AS n"
    sql = f"""
        SELECT {sel}, {order}, count() AS src_rows
        FROM {proxy} {where}
        GROUP BY {sel}
        HAVING ({sel}) NOT IN (SELECT {sel} FROM {target} {where} GROUP BY {sel})
        ORDER BY 1 LIMIT {MAX_MISSING_KEYS_LISTED}
        {ODBC_SETTINGS}
    """
    return cols, client.query(sql).result_rows


# ---------------------------------------------------------------- 對帳主體

def classify(ch_count, src_count, tolerance_pct, ok_label):
    """完全相符為 ok_label；差距在容忍值內視為邊界效應（cutoff 切在邊界那一秒）。"""
    if ch_count == src_count:
        return ok_label
    if src_count and abs(ch_count - src_count) * 100.0 / src_count <= tolerance_pct:
        return "OK_BOUNDARY"
    return "GAP"


def audit_table(client, table_key, cfg, args):
    """對帳單一表，回傳結果 dict。"""
    target = cfg["target"]
    time_col = cfg.get("time_col")
    sort_key = get_sorting_key(client, target)
    cutoff = resolve_cutoff(client, target, args.cutoff)

    if time_col:
        # 下界不可早於 history_start，否則會把「本來就不同步的歷史」算成缺口
        lower = (f"greatest(toDateTime('{cutoff}') - INTERVAL {args.window_days} DAY, "
                 f"toDateTime('{cfg['history_start']}'))"
                 if cfg.get("history_start")
                 else f"toDateTime('{cutoff}') - INTERVAL {args.window_days} DAY")
        where = f"WHERE {time_col} >= {lower} AND {time_col} < toDateTime('{cutoff}')"
    else:
        where = ""

    result = {"table": table_key, "source": cfg["source"], "target": target,
              "cutoff": cutoff, "note": "", "missing_keys": None}
    proxy = build_odbc_proxy(client, table_key, cfg)
    t0 = time.perf_counter()
    try:
        ch_max, src_max, lag = measure_lag(client, proxy, target, time_col)
        result.update({"ch_max": ch_max, "src_max": src_max, "lag_seconds": lag})
        result["stale"] = lag is not None and lag > args.stale_hours * 3600

        src_rows = client.command(f"SELECT count() FROM {proxy} {where} {ODBC_SETTINGS}")
        ch_dedup = client.command(f"SELECT uniqExact({sort_key}) FROM {target} {where}")
        result.update({"source_rows": src_rows, "ch_dedup": ch_dedup, "sort_key": sort_key})

        if src_rows == 0:
            result["verdict"], result["pct"] = "NO_SOURCE_DATA", 100.0
        elif ch_dedup == src_rows:
            result["verdict"], result["pct"] = "OK", 100.0
        elif not sort_key_available(sort_key, cfg["engine_ddl"]):
            result["verdict"], result["pct"] = "SKIP_NO_KEY", 0.0
            result["note"] = "排序鍵欄位未同步，無法在來源端同鍵去重"
        elif table_key in NON_UNIQUE_KEY_TABLES:
            # 列數對不上但排序鍵已知非唯一 —— 改判鍵層級完整度（來源端也去重）
            logger.info(f"  {table_key}: 排序鍵非唯一，改查來源端鍵層級筆數（較慢）...")
            src_keys = client.command(
                f"SELECT uniqExact({sort_key}) FROM {proxy} {where} {ODBC_SETTINGS}")
            result["source_keys"] = src_keys
            result["pct"] = ch_dedup * 100.0 / src_keys if src_keys else 100.0
            result["verdict"] = classify(ch_dedup, src_keys, args.tolerance_pct, "OK_KEY_COLLAPSE")
        else:
            result["pct"] = ch_dedup * 100.0 / src_rows
            result["verdict"] = classify(ch_dedup, src_rows, args.tolerance_pct, "OK")

        # 停滯的表即使範圍內 100% 也沒有意義，改判 STALE 讓它浮出來
        if result["stale"]:
            result["verdict"] = "STALE"

        # 有缺漏才去查是缺哪些鍵（NOT IN 子查詢很貴）
        if result["verdict"] in ("GAP", "OK_BOUNDARY") and sort_key_available(sort_key, cfg["engine_ddl"]):
            try:
                result["missing_keys"] = find_missing_keys(
                    client, proxy, target, sort_key, where, time_col)
            except Exception as e:
                logger.warning(f"  {table_key}: 缺漏鍵查詢失敗：{mask_secrets(e)[:150]}")

    except Exception as e:
        result.update({"verdict": "ERROR", "pct": 0.0, "source_rows": 0, "ch_dedup": 0,
                       "stale": False, "lag_seconds": None,
                       "note": mask_secrets(e)[:200]})
    finally:
        result["elapsed"] = time.perf_counter() - t0
        try:
            client.command(f"DROP TABLE IF EXISTS {proxy}")
        except Exception as cleanup_err:
            logger.warning(f"  無法清除代理表 {proxy}: {mask_secrets(cleanup_err)}")
    return result


# ---------------------------------------------------------------- 報表輸出

def category_of(table_key):
    for name, keys in TABLE_CATEGORIES:
        if table_key in keys:
            return name
    return "其他"


def report_source_rows(r):
    """
    報表用的「來源端筆數」。排序鍵非唯一的表改用來源端「同鍵去重後」的筆數當基準，
    兩邊基準一致，未同步筆數才會如實反映缺漏（見檔頭設計重點 3）。
    """
    return r.get("source_keys", r.get("source_rows", 0))


def format_pct(pct, missing):
    """
    只有「一筆不差」才准顯示 100.00%。否則 848,875/848,876 會被四捨五入成 100.00%，
    和同一列的「未同步筆數 1」自相矛盾。
    """
    if missing == 0:
        return "100.00%"
    if missing > 0:
        return f"{min(pct, 99.9999):.4f}%"
    return f"{pct:.4f}%"   # CH 比來源多（邊界效應），如實顯示 >100%


def format_lag(seconds):
    if seconds is None:
        return "n/a"
    if abs(seconds) < 3600:
        return f"{seconds}s"
    return f"{seconds / 86400:.2f}d"


def report_note(r):
    """報表備註：只保留讀報表的人需要知道的結論。"""
    if r["verdict"] == "ERROR":
        return f"查詢失敗：{r.get('note', '')[:80]}"
    if r["verdict"] == "SKIP_NO_KEY":
        return r.get("note", "")
    if r["verdict"] == "STALE":
        return f"資料停滯，落後 {format_lag(r.get('lag_seconds'))}，完成度數字不具意義"
    if r["verdict"] == "OK_KEY_COLLAPSE":
        collapsed = r.get("source_rows", 0) - r.get("source_keys", 0)
        return (f"來源含重複鍵 {collapsed:,} 列（ReplacingMergeTree 既定折疊，非漏同步）；"
                f"已改用去重後筆數比對。{NON_UNIQUE_KEY_TABLES.get(r['table'], '')}")
    if r["verdict"] == "OK_BOUNDARY":
        return "差異在容忍值內（cutoff 邊界效應），詳見下方缺漏鍵明細"
    if r["verdict"] == "GAP":
        return "確有缺漏，詳見下方缺漏鍵明細"
    return ""


def build_report_rows(results, table_configs):
    """組出報表列（依 TABLE_CATEGORIES 的分類與順序），最後附總計列。"""
    by_key = {r["table"]: r for r in results}
    ordered = [k for _, keys in TABLE_CATEGORIES for k in keys if k in by_key]
    ordered += [k for k in by_key if k not in ordered]

    rows = []
    for key in ordered:
        r = by_key[key]
        src, ch = report_source_rows(r), r.get("ch_dedup", 0)
        rows.append({
            "category": category_of(key),
            "source_table": table_configs[key]["source"],
            "source_rows": src,
            "target_table": table_configs[key]["target"],
            "target_rows": ch,
            "missing": src - ch,
            "pct": 100.0 if src == 0 else ch * 100.0 / src,
            "note": report_note(r),
        })

    tot_src = sum(x["source_rows"] for x in rows)
    tot_ch = sum(x["target_rows"] for x in rows)
    rows.append({
        "category": "總計", "source_table": f"{len(rows)} 張表",
        "source_rows": tot_src, "target_table": "", "target_rows": tot_ch,
        "missing": tot_src - tot_ch,
        "pct": 100.0 if tot_src == 0 else tot_ch * 100.0 / tot_src,
        "note": "",
    })
    return rows


def missing_key_sections(results):
    """把各表的缺漏鍵整理成 (表名, 欄位名清單, 資料列) 供報表與 CSV 共用。"""
    sections = []
    for r in results:
        if not r.get("missing_keys"):
            continue
        cols, rows = r["missing_keys"]
        if rows:
            sections.append((r["table"], r.get("sort_key", ""), cols, rows))
    return sections


def display_width(s):
    """中日韓字元在終端佔兩格，len() 會低估寬度導致表格錯位。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, width, right=False):
    fill = " " * max(width - display_width(s), 0)
    return (fill + s) if right else (s + fill)


def print_report(rows, sections, scope_note):
    w = [14, 50, 14, 42, 14, 12, 11]
    head = ["分類", "(來源端)MSSQL 表名", "來源端筆數", "(目的端)ClickHouse 表名",
            "目的端筆數", "未同步筆數", "同步百分比"]
    rule = "-" * (sum(w) + 2 * len(w))
    print(f"\n【每日同步對帳報表】{scope_note}\n")
    print("  ".join(pad(h, x) for h, x in zip(head, w)))
    print(rule)
    for x in rows:
        if x["category"] == "總計":
            print(rule)
        print("  ".join([
            pad(x["category"], w[0]), pad(x["source_table"], w[1]),
            pad(f"{x['source_rows']:,}", w[2], right=True),
            pad(x["target_table"], w[3]),
            pad(f"{x['target_rows']:,}", w[4], right=True),
            pad(f"{x['missing']:,}", w[5], right=True),
            pad(format_pct(x["pct"], x["missing"]), w[6], right=True),
        ]))

    notes = [x for x in rows if x["note"]]
    if notes:
        print("\n【備註】")
        for x in notes:
            print(f"  * {x['source_table'].split('.')[-1]}：{x['note']}")

    if sections:
        print("\n【缺漏鍵明細】未同步筆數對應的實際鍵值")
        for table_key, sort_key, cols, data in sections:
            print(f"\n  {table_key}  排序鍵 = ({sort_key})")
            print("    " + " | ".join(cols + ["來源最早時間", "來源列數"]))
            for row in data:
                print("    " + " | ".join(str(v) if str(v) != "" else "(空)" for v in row))


def write_csv(rows, sections, path, scope_note):
    """
    輸出 CSV。寫檔失敗（最常見是上一份報表還開在 Excel 裡鎖住檔案）不可讓整個程式崩潰——
    對帳要跑約 3 分鐘，報表內容已經印在畫面上，不該因為寫不了檔就把結果全丟掉。
    """
    try:
        _write_csv(rows, sections, path, scope_note)
    except OSError as e:
        logger.error(f"CSV 寫入失敗（{e.__class__.__name__}: {e}）。"
                     f"若該檔正開在 Excel 中請先關閉，或改用 --csv 指定其他路徑。"
                     f"報表內容已完整輸出於上方，可直接複製。")


def _write_csv(rows, sections, path, scope_note):
    # utf-8-sig：Excel 直接開啟才不會把中文變亂碼
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([f"每日同步對帳報表 {scope_note}"])
        writer.writerow(["分類", "(來源端)MSSQL表名", "來源端筆數", "(目的端)ClickHouse表名",
                         "目的端筆數", "未同步筆數", "同步百分比", "備註"])
        for x in rows:
            writer.writerow([x["category"], x["source_table"], x["source_rows"],
                             x["target_table"], x["target_rows"], x["missing"],
                             format_pct(x["pct"], x["missing"]), x["note"]])
        if sections:
            writer.writerow([])
            writer.writerow(["【缺漏鍵明細】未同步筆數對應的實際鍵值"])
            for table_key, sort_key, cols, data in sections:
                writer.writerow([])
                writer.writerow([f"{table_key}", f"排序鍵 = ({sort_key})"])
                writer.writerow(cols + ["來源最早時間", "來源列數"])
                for row in data:
                    writer.writerow([str(v) if str(v) != "" else "(空)" for v in row])
    logger.info(f"CSV 已輸出：{path}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    args = parse_args()

    if not os.getenv("MSSQL_PASSWORD"):
        logger.error("MSSQL_PASSWORD 未設定，ODBC 連線會失敗（且錯誤訊息不易辨識）")
        sys.exit(1)

    table_configs = load_configs(args.config)
    if args.table:
        if args.table not in table_configs:
            logger.error(f"未知的表：{args.table}。可用：{', '.join(table_configs)}")
            sys.exit(1)
        targets = [args.table]
    else:
        targets = list(table_configs)

    client = get_client()
    logger.info(f"對帳 {len(targets)} 張表；cutoff={args.cutoff}，batch 表窗口={args.window_days} 天")

    results = []
    for table_key in targets:
        logger.info(f"-> {table_key}")
        results.append(audit_table(client, table_key, table_configs[table_key], args))

    scope_note = (f"（統計範圍：batch 表取 cutoff 前 {args.window_days} 天，full 表取整表；"
                  f"cutoff={args.cutoff}）")
    report_rows = build_report_rows(results, table_configs)
    sections = missing_key_sections(results)

    print_report(report_rows, sections, scope_note)
    if args.csv:
        write_csv(report_rows, sections, args.csv, scope_note)

    bad = [r for r in results if r["verdict"] in ("GAP", "ERROR", "SKIP_NO_KEY", "STALE")]
    if bad:
        logger.warning(f"{len(bad)}/{len(results)} 張表未通過：" + ", ".join(r["table"] for r in bad))
        if args.strict:
            sys.exit(1)
    else:
        logger.info(f"全部 {len(results)} 張表通過對帳")


if __name__ == "__main__":
    main()
