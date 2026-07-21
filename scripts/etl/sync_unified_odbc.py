#!/usr/bin/env python3
"""
Unified Sync Script for All Bronze Tables (Flowable + MDM + HR)
Syncs data from MSSQL to ClickHouse Bronze layer using native ODBC Table Engine.

Fully refactored to use `ENGINE = ODBC(...)` explicitly typed tables,
completely bypassing the MS-ODBC driver's unstable dynamic auto-discovery
that causes deadlocks on LOB (varchar(max)/xml) columns!
"""

import sys
import logging
import re
import time
import argparse
import os
import yaml
from pathlib import Path
from datetime import datetime, timedelta
import clickhouse_connect
from clickhouse_connect.driver.summary import QuerySummary
from setup_schema import execute_sql_file

# ClickHouse Configuration
CLICKHOUSE_CONFIG = {
    "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
    "port": int(os.environ.get("CLICKHOUSE_PORT", "8123")),
    "username": os.getenv("CLICKHOUSE_USERNAME", "default"),
    "password": os.getenv("CLICKHOUSE_PASSWORD", "<CLICKHOUSE_PASSWORD>"),
    "database": os.getenv("CLICKHOUSE_DATABASE", "default"),
    "send_receive_timeout": int(os.getenv("CLICKHOUSE_TIMEOUT", "3600")), # Increased to 1 hour
    "connect_timeout": 30,
    # 關閉 bridge 連線池，避免壞死連線被後續查詢重用而拋 IMC06/629。
    # ⚠ 必須從這裡傳；寫在 SQL 尾端 SETTINGS 子句不會生效。
    "settings": {"odbc_bridge_use_connection_pooling": 0},
}

# MSSQL ODBC Credentials
MSSQL_USER = os.getenv("MSSQL_USER", "APP_SRV_BPM")
MSSQL_PASSWORD = os.getenv("MSSQL_PASSWORD", "")
ODBC_DSN = os.getenv("ODBC_DSN", "MSSQL_DSN")

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class StaleOdbcConnectionError(Exception):
    """
    IMC06「connection is broken and recovery is not possible」(code 86)。重試或切窗都救不了，
    只有重啟 bridge 能清除。根因是 MARS 停用了連線復原，已由 build_odbc_conn 的
    MARS_Connection=no 解決；此類別保留為防線，若再出現代表有新的成因。
    """
    pass


def is_stale_odbc_connection_error(err_msg: str) -> bool:
    """Detects the IMC06 stale-pooled-connection failure mode in an exception message."""
    return "IMC06" in err_msg or "connection is broken and recovery is not possible" in err_msg


def has_error_code(err_msg: str, code: int) -> bool:
    """
    判斷例外訊息是否對應某個 ClickHouse 錯誤碼。

    clickhouse_connect 的例外沒有錯誤碼欄位，只能讀訊息文字，而格式有兩種：
    driver 外層 `received ClickHouse error code 1000` / `exception, code: 1000`（小寫、
    冒號時有時無），server 內層 `Code: 1000. DB::Exception:`（大寫）。傳輸中斷失敗常
    只有外層，舊版寫死比對 "Code: 1000" 因此完全打不中，保護形同虛設。
    """
    return re.search(rf"code:?\s*{code}\b", err_msg, re.IGNORECASE) is not None


# 連線池關閉設定不放這裡——實測寫在 SQL SETTINGS 子句不生效，改由 CLICKHOUSE_CONFIG 傳。
ODBC_QUERY_SETTINGS = "SETTINGS max_execution_time = 3600"


STALE_ODBC_HINT = (
    "ODBC bridge connection pool is stale (IMC06 unrecoverable) — retrying or splitting the "
    "batch window will not fix this. Restart the bridge: `docker exec clickhouse-server-odbc "
    "pkill -f clickhouse-odbc-bridge` then re-run this sync."
)


def written_rows_of(insert_result, context=""):
    """
    取本次 INSERT 自來源抓取的列數（ClickHouse X-ClickHouse-Summary header）。

    不用 `SELECT count()` 對區間計數：watermark 以 max_data_time 續跑會刻意讓區間重疊
    （見 get_last_watermark），該 count 會把已同步的列算進去而灌水。

    ⚠ 這是「抓取數」不是「落地數」：optimize_on_insert 會在寫入當下就套用 ReplacingMergeTree
      收斂，排序鍵相同的列被折疊卻仍計入。實測 written_rows 1,142,277 → 實際落地 783,799。
      故只可用於觀察 I/O 量，**不可拿來對帳**；完整性請看 sync_full Step 3 的實際計數。
    """
    if isinstance(insert_result, QuerySummary):
        return insert_result.written_rows
    logger.warning(
        f"  [written_rows] INSERT{(' ' + context) if context else ''} did not return a "
        f"QuerySummary (got {type(insert_result).__name__}); row count unavailable, reporting 0."
    )
    return 0


def parse_source(source_str):
    """
    解析來源字串為資料庫、結構描述與資料表名稱。
    例如將 'APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108' 解析出對應的 dict。
    """
    parts = source_str.split(".")
    if len(parts) == 3:
        return {"db": parts[0], "schema": parts[1], "table": parts[2]}
    elif len(parts) == 2:
        return {"db": parts[0], "schema": "dbo", "table": parts[1]}
    else:
        return {"db": "APP_SRV_BPM", "schema": "dbo", "table": parts[0]}

def build_odbc_conn(db_name):
    """
    建立針對特定資料庫的 ODBC 連線字串。

    ⚠ MARS_Connection 必須為 no：MARS 會停用 SQL Server 的 connection resiliency，網路稍有
    波動就把連線標記 unrecoverable 並拋 IMC06（錯誤訊息「No attempt was made to restore the
    connection」即為證據）。本腳本每條連線只跑一個查詢，不需要 MARS。
    """
    return f"DSN={ODBC_DSN};Database={db_name};Uid={MSSQL_USER};Pwd={MSSQL_PASSWORD};MARS_Connection=no"


def load_configs(config_name="sync_tables.yaml"):
    """
    載入 YAML 設定檔，包含所有需要同步的表格定義、主鍵及同步策略 (batch/full)。
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config", config_name)
    logger.info(f"Using layout config: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"找不到設定檔：{config_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"讀取 YAML 發生錯誤：{e}")
        sys.exit(1)

def get_client():
    return clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)


def generate_batches(start_str, end_date_str, step_days=7, step_hours=0):
    """
    依據給定的起始與結束時間，按照指定的天數或小時數切割時間區間，
    產生批次同步用的時間對 (start, end) 列表。
    """
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")

    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        if len(end_date_str) == 10:
            end_date = end_date + timedelta(days=1, microseconds=-1)

    current_date = start_date
    batches = []
    step_delta = timedelta(days=step_days)
    if step_hours > 0:
        step_delta = timedelta(hours=step_hours)

    while current_date < end_date:
        next_date = current_date + step_delta
        if next_date > end_date:
            next_date = end_date
        batches.append((current_date.strftime("%Y-%m-%d %H:%M:%S"), next_date.strftime("%Y-%m-%d %H:%M:%S")))
        current_date = next_date

    return batches


def setup_watermark_table(client, db_name):
    """
    在指定 database 建立 _sync_watermark 並自動遷移 min/max_data_time 欄位。
    db_name 由呼叫端依 target 前綴推導，不可寫死。
    """
    sql = f"""
    CREATE TABLE IF NOT EXISTS {db_name}._sync_watermark (
        table_name String,
        last_sync_time DateTime64(3),
        sync_time DateTime64(3),
        row_count UInt64,
        duration_ms Float64,
        min_data_time Nullable(DateTime64(3)) COMMENT 'Data Minimum Timestamp',
        max_data_time Nullable(DateTime64(3)) COMMENT 'Data Maximum Timestamp'
    ) ENGINE = ReplacingMergeTree(sync_time)
    ORDER BY (table_name)
    """
    client.command(sql)
    
    # Auto Migration: Ensure columns exist in case the table already existed
    try:
        client.command(f"ALTER TABLE {db_name}._sync_watermark ADD COLUMN IF NOT EXISTS min_data_time Nullable(DateTime64(3)) COMMENT 'Data Minimum Timestamp'")
        client.command(f"ALTER TABLE {db_name}._sync_watermark ADD COLUMN IF NOT EXISTS max_data_time Nullable(DateTime64(3)) COMMENT 'Data Maximum Timestamp'")
    except Exception as e:
        logger.warning(f"Failed to auto-migrate watermark columns on {db_name}._sync_watermark: {e}")


def update_watermark(client, table_name, last_sync_time_str, row_count, duration_ms=0, min_data_time=None, max_data_time=None):
    """
    當一個批次或全量同步成功後，將同步資訊寫入 watermark 表。
    利用 ReplacingMergeTree(sync_time) 的特性，確保相同 table_name 最終只保留最新的水位資訊。
    """
    try:
        ts_val = last_sync_time_str
        if len(ts_val) == 10:
            ts_val += " 00:00:00"
            
        min_val = f"CAST('{min_data_time}', 'Nullable(DateTime64(3))')" if min_data_time else "NULL"
        max_val = f"CAST('{max_data_time}', 'Nullable(DateTime64(3))')" if max_data_time else "NULL"
        
        db_name = table_name.split('.')[0]
        sql = f"""
        INSERT INTO {db_name}._sync_watermark (table_name, last_sync_time, sync_time, row_count, duration_ms, min_data_time, max_data_time)
        VALUES ('{table_name}', CAST('{ts_val}', 'DateTime64(3)'), now(), {row_count}, {duration_ms}, {min_val}, {max_val})
        """
        client.command(sql)
        logger.info(f"  Watermark updated for {table_name}: {last_sync_time_str} (Data min: {min_data_time}, max: {max_data_time})")
    except Exception as e:
        logger.warning(f"  Failed to update watermark: {e}")


def get_last_watermark(client, table_name):
    """
    取得續跑接續點（FINAL 確保拿到背景尚未合併的最新版本）。

    以 max_data_time（實際資料前緣）為主、last_sync_time（掃描邊界）為備案：後者可能遠超實際
    資料（掃到今天但資料只到 5/19），若來源日後補進那段曾是空的區間，從掃描邊界續跑會靜默漏掉。
    從資料前緣續跑會重掃出重疊批次，由各表 ReplacingMergeTree 去重鍵吸收。
    """
    try:
        db_name = table_name.split('.')[0]
        sql = (
            f"SELECT ifNull(maxOrNull(max_data_time), maxOrNull(last_sync_time)) "
            f"FROM {db_name}._sync_watermark FINAL WHERE table_name = '{table_name}'"
        )
        result = client.query(sql)
        if result.result_rows and result.result_rows[0][0]:
            dt = result.result_rows[0][0]
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.warning(f"Could not fetch watermark for {table_name}: {e}")
    return None


def query_data_min_max(client, table_name, time_col, known_min=None):
    """
    查詢表內實際資料的時間跨度，供 watermark 記錄。

    傳入 known_min 時只查 max：正向批次同步中 min 一旦非空就不會再變，而 time_col 多半不在
    ORDER BY 前綴，每批重算 min 等於多做一次整欄掃描。
    """
    if not time_col:
        return None, None

    def fmt(dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None

    try:
        if known_min:
            res = client.query(f"SELECT maxOrNull({time_col}) FROM {table_name}")
            return known_min, (fmt(res.result_rows[0][0]) if res.result_rows else None)

        res = client.query(f"SELECT minOrNull({time_col}), maxOrNull({time_col}) FROM {table_name}")
        if res.result_rows and res.result_rows[0]:
            return fmt(res.result_rows[0][0]), fmt(res.result_rows[0][1])
    except Exception as e:
        logger.warning(f"Failed to query data min/max for {table_name}: {e}")
    return known_min, None


def get_source_min_time(config):
    """
    取得歷史同步起點（僅在沒有 watermark 時使用）：config 的 history_start，無則退回 2025-01-01。

    刻意不動態查來源 MIN(time_col)：ClickHouse 不會把聚合下推到 MSSQL，`min()` 打在 ENGINE=ODBC
    表上會把整個時間欄拉回本地才聚合（大表等同全欄掃描），且偏偏發生在 ODBC 壓力最大的時刻。
    來源庫唯讀、odbc() table function 也不接受 raw SQL，無可用下推路徑。
    """
    history_start = config.get('history_start')
    if history_start:
        ts = f"{history_start} 00:00:00" if len(str(history_start)) == 10 else str(history_start)
        logger.info(f"  [History Start] Using configured history_start: {ts}")
        return ts

    logger.info("  [ODBC Safety] Using default historical floor 2025-01-01 00:00:00")
    return "2025-01-01 00:00:00"


def sync_batch(client, config, start_str, end_str):
    """
    執行單次批次同步 (依賴時間區間擷取來源資料)。
    若發生 OOM 或 Timeout 錯誤，將直接拋出例外，交由外層進行自適應切割。
    若為一般連線錯誤則進行自動重試 (最多 3 次)，並重置 client 連線以避開死鎖。
    """
    target = config['target']
    time_col = config['time_col']
    cols = config.get('columns', '*')
    source_table_ref = config['source_table_ref']
    batch_id = f"{start_str}_{end_str}"

    logger.info(f"Processing Batch: {start_str} to {end_str}")

    select_clause = "*" if cols == '*' else cols

    insert_sql = f"""
    INSERT INTO {target}
    SELECT {select_clause},
           '{batch_id}' as _batch_id,
           now() as _extracted_at,
           1 as _sync_version
    FROM {source_table_ref}
    WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}'
    {ODBC_QUERY_SETTINGS}
    """

    max_retries = 3
    retry_delay = 30
    current_client = client

    try:
        for attempt in range(max_retries):
            start_time = time.perf_counter()
            try:
                insert_result = current_client.command(insert_sql)
                duration = time.perf_counter() - start_time
                duration_ms = duration * 1000
                count = written_rows_of(insert_result, context=f"batch {batch_id}")
                # 用「fetched」而非「synced」：實際落地列數會因收斂而較少（見 written_rows_of）
                logger.info(f"  Fetched {count:,} rows from source in {duration:.2f}s")
                return count, duration_ms
            except Exception as e:
                err_msg = str(e)

                # 毒池：重試與切窗都救不了，快速失敗並提示修法，避免每批空燒 ~90s
                if is_stale_odbc_connection_error(err_msg):
                    logger.error(f"  {STALE_ODBC_HINT}")
                    raise StaleOdbcConnectionError(err_msg) from e

                logger.warning(f"  Batch failed (Attempt {attempt + 1}/{max_retries}): {err_msg}")

                # 原地重試無效、只有切窗有救的錯誤，第一次失敗就交給 adaptive split
                # （629 傳輸中斷實測：重試 6 敗、切窗 4 勝）。其餘錯誤仍保留 3 次重試。
                is_oom = has_error_code(err_msg, 241) or "MEMORY_LIMIT" in err_msg
                is_transport = ("Timeout" in err_msg
                                or has_error_code(err_msg, 1000)
                                or has_error_code(err_msg, 629))
                if is_oom or is_transport:
                    logger.warning("  Retry at this window size cannot help. Aborting retries to trigger adaptive range splitting.")
                    raise e

                if attempt < max_retries - 1:
                    logger.info("  Refreshing client session to avoid session locks...")
                    # 只關自建的 client；關掉呼叫端傳入的會讓 main() 後續查詢全落在死連線上
                    if current_client is not client:
                        try: current_client.close()
                        except Exception: pass
                    current_client = get_client()
                    time.sleep(retry_delay)
                else:
                    logger.error(f"  All retries failed for batch {batch_id}")
                    raise e
    finally:
        # 收掉重試過程中自建的連線，避免每次重試各留一條 HTTP session
        if current_client is not client:
            try: current_client.close()
            except Exception: pass


def sync_batch_adaptive(client, config, start_str, end_str):
    """
    自適應批次同步機制 (Adaptive Splitting)。
    當呼叫 sync_batch 失敗且判斷為負載過高時，會將當前時間區間對半切 (Split into two half chunks)，
    遞迴重新嘗試，直到區間小於 30 分鐘為止。這能有效避免巨量資料造成 ODBC Buffer Overflow。
    """
    try:
        return sync_batch(client, config, start_str, end_str)
    except StaleOdbcConnectionError:
        # Splitting the window can't fix a poisoned connection pool — re-raise immediately.
        raise
    except Exception as e:
        logger.warning(f"Batch {start_str} to {end_str} failed. Checking if we can split...")
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        diff = end_dt - start_dt

        if diff < timedelta(minutes=30):
            logger.error(f"  Range too small to split ({diff}). Aborting this block.")
            raise e

        mid_dt = start_dt + (diff / 2)
        mid_str = mid_dt.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"  Splitting: {start_str} -> {mid_str} AND {mid_str} -> {end_str}")

        count1, dur1 = sync_batch_adaptive(client, config, start_str, mid_str)
        count2, dur2 = sync_batch_adaptive(client, config, mid_str, end_str)
        return count1 + count2, dur1 + dur2


def sync_full(client, config):
    """
    全量同步：建暫存表 → INSERT → 驗證行數 > 0 → 原子替換（RENAME 原表為舊表 → RENAME 暫存表
    為目標表 → DROP 舊表）。

    取代舊的 TRUNCATE + INSERT：任何一步失敗，原表都完整保留（2026-06 曾因 INSERT 失敗留下
    15 張空表）。替換中途失敗會 rollback；rollback 也失敗時保留舊表供人工恢復。
    """
    target = config['target']
    cols = config.get('columns', '*')
    source_table_ref = config['source_table_ref']
    range_col = config.get('range_col')
    range_batches = config.get('range_batches')

    logger.info(f"Full Syncing (Safe Mode): {target}")
    select_clause = "*" if cols == '*' else cols

    # 時間戳確保暫存表名唯一
    temp_table = f"{target}_tmp_{int(time.time() * 1000)}"
    old_table = f"{target}_old_{int(time.time() * 1000)}"

    # 替換期間，原表資料會短暫只存在於 old_table。此旗標為 True 時代表 old_table 是
    # 原表的「唯一副本」，任何清理路徑都嚴禁刪除它，否則會把原始資料徹底刪光。
    original_only_in_old = False

    try:
        # CREATE TABLE ... AS other_table 只複製結構；不可加 LIMIT 0（SYNTAX_ERROR 62）
        logger.info(f"  [Step 1] Creating temp table: {temp_table}")
        client.command(f"CREATE TABLE {temp_table} AS {target}")

        if range_batches and range_col:
            # 步驟 2a：按範圍分批插入
            logger.info(f"  [Step 2a] Range Batch: {len(range_batches)} batches using {range_col}")
            total_count = 0
            total_duration = 0
            for i, (range_start, range_end) in enumerate(range_batches, 1):
                batch_id = f"full_sync_{datetime.now().strftime('%Y%m%d')}_{i}"
                insert_sql = f"""
                INSERT INTO {temp_table}
                SELECT {select_clause},
                       '{batch_id}' as _batch_id,
                       now() as _extracted_at,
                       1 as _sync_version
                FROM {source_table_ref}
                WHERE {range_col} >= '{range_start}' AND {range_col} < '{range_end}'
                {ODBC_QUERY_SETTINGS}
                """
                start_time = time.perf_counter()
                insert_result = client.command(insert_sql)
                duration = (time.perf_counter() - start_time) * 1000
                total_duration += duration
                count = written_rows_of(insert_result, context=f"{target} range {range_start}-{range_end}")
                total_count += count
                logger.info(f"    Batch {i}/{len(range_batches)} [{range_start}-{range_end}]: {count:,} rows in {duration/1000:.2f}s")

            written_total = total_count
            insert_duration = total_duration
        else:
            # 步驟 2b：一次性全量插入
            logger.info("  [Step 2b] Full Insert (single batch)")
            start_t = time.perf_counter()
            insert_sql = f"""
            INSERT INTO {temp_table}
            SELECT {select_clause},
                   'full_sync_{datetime.now().strftime("%Y%m%d")}' as _batch_id,
                   now() as _extracted_at,
                   1 as _sync_version
            FROM {source_table_ref}
            {ODBC_QUERY_SETTINGS}
            """
            insert_result = client.command(insert_sql)
            insert_duration = (time.perf_counter() - start_t) * 1000
            written_total = written_rows_of(insert_result, context=target)

        # 「絕不留空表」最後防線。必須用實際 count() 而非 written_rows——後者取不到值時會回 0，
        # 會把本來成功的同步誤判為空而整批捨棄。本地查詢、每表一次，成本可忽略。
        row_count = client.command(f"SELECT count() FROM {temp_table}")
        logger.info(f"  [Step 3] Validation: {row_count:,} rows in temp table (written_rows reported {written_total:,})")
        if row_count == 0:
            error_msg = f"Temp table {temp_table} has 0 rows - INSERT produced no data (source may be empty or query failed)"
            logger.error(error_msg)
            # 清理暫存表（失敗情況）
            client.command(f"DROP TABLE IF EXISTS {temp_table}")
            raise ValueError(error_msg)

        logger.info("  [Step 4] Atomic replacement")
        try:
            # 改表名要用獨立的 RENAME TABLE，ClickHouse 無 ALTER TABLE ... RENAME TO（SYNTAX_ERROR 62）
            client.command(f"RENAME TABLE {target} TO {old_table}")
            original_only_in_old = True   # 此後原表資料僅存於 old_table
            client.command(f"RENAME TABLE {temp_table} TO {target}")
            original_only_in_old = False  # 新表就位，old_table 不再是唯一副本
            client.command(f"DROP TABLE IF EXISTS {old_table}")
            logger.info("  [Step 4] ✅ Replacement successful")
        except Exception as e:
            logger.error(f"  [Step 4] ❌ Replacement failed: {e}. Attempting rollback...")
            if original_only_in_old:
                try:
                    client.command(f"RENAME TABLE {old_table} TO {target}")
                    original_only_in_old = False
                    logger.info(f"  [Rollback] ✅ Original table restored")
                except Exception as rb_err:
                    logger.error(
                        f"  [Rollback] ❌ Failed to restore original table: {rb_err}. "
                        f"原表資料目前僅存於 {old_table}，已保留不刪除，需人工介入處理！"
                    )
            raise

        logger.info("  [Step 5] Updating watermark")
        min_dt, max_dt = query_data_min_max(client, target, config.get('time_col'))
        update_watermark(client, target, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row_count, insert_duration, min_dt, max_dt)

        logger.info(f"  ✅ Full sync complete: {row_count:,} rows in {insert_duration/1000:.2f}s")
        return row_count

    except Exception as e:
        err_msg = str(e)
        if is_stale_odbc_connection_error(err_msg):
            logger.error(f"  {STALE_ODBC_HINT}")
        else:
            logger.error(f"  Full sync failed: {err_msg}")

        # old_table 只有在確定「不是原表唯一副本」時才可刪，否則等於把原始資料刪光
        try:
            client.command(f"DROP TABLE IF EXISTS {temp_table}")
        except Exception:
            pass
        if original_only_in_old:
            logger.error(
                f"  [Cleanup] 保留 {old_table}（原表唯一副本，rollback 失敗），不予刪除。"
                f"請人工確認後執行：RENAME TABLE {old_table} TO {target}"
            )
        else:
            try:
                client.command(f"DROP TABLE IF EXISTS {old_table}")
            except Exception:
                pass

        if is_stale_odbc_connection_error(err_msg) and not isinstance(e, StaleOdbcConnectionError):
            raise StaleOdbcConnectionError(err_msg) from e
        raise


def main():
    # Stage-1: parse --config only so we can load TABLE_CONFIGS before defining --table choices.
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", default="sync_tables.yaml")
    pre_args, _ = pre_parser.parse_known_args()

    table_configs = load_configs(pre_args.config)

    # Stage-2: full argument parsing with proper --table choices derived from config.
    parser = argparse.ArgumentParser(description="Unified ODBC Sync using Explicit Table Engines")
    parser.add_argument("--table", choices=list(table_configs.keys()) + ['all'], default='all', help="Table to sync")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    parser.add_argument("--step-days", type=int, default=7, help="Batch size in days")
    parser.add_argument("--step-hours", type=int, default=0, help="Batch size in hours")
    parser.add_argument("--config", default="sync_tables.yaml", help="YAML config file name in config dir")
    parser.add_argument("--dry-run", action="store_true", help="Print batches without executing")

    args = parser.parse_args()

    client = get_client()

    tables_to_sync = [args.table] if args.table != 'all' else list(table_configs.keys())
    logger.info(f"Target Tables: {', '.join(tables_to_sync)}")

    for db_name in sorted({table_configs[t]['target'].split('.')[0] for t in tables_to_sync}):
        setup_watermark_table(client, db_name)

    stats = []

    for table_key in tables_to_sync:
        start_t = time.time()
        status = "SUCCESS"
        row_count = 0
        config = table_configs[table_key]
        target_table = config['target']

        src = parse_source(config['source'])
        conn_str = build_odbc_conn(src['db'])

        logger.info(f"\n{'='*60}")
        logger.info(f"Starting Sync for: {table_key.upper()}")
        logger.info(f"  Source (MSSQL): {config['source']}  ->  Target (ClickHouse): {target_table}")

        # Ensure pure explicit ODBC table proxy creation!
        temp_name = f"odbc_temp_{table_key}"

        try:
            # 放 try 內而非直接 raise：才能走既有的 summary/exit(1) 流程並清掉臨時 ODBC 表
            engine_ddl = config.get('engine_ddl')
            if not engine_ddl:
                raise ValueError(
                    f"Missing engine_ddl for {table_key}. "
                    f"All tables MUST use explicit ddl schemas in sync_tables.yaml!"
                )

            if not args.dry_run:
                client.command(f"DROP TABLE IF EXISTS {temp_name}")
                create_sql = f"""
                CREATE TABLE {temp_name} (
                    {engine_ddl}
                ) ENGINE = ODBC('{conn_str}', '{src['schema']}', '{src['table']}')
                """
                client.command(create_sql)
                config['source_table_ref'] = temp_name
                logger.info(f"  [DDL Bypass] Created explicit Safe Table Engine: {temp_name}")
            else:
                config['source_table_ref'] = temp_name

            if config['strategy'] == 'full':
                if not args.dry_run:
                    row_count = sync_full(client, config)
                else:
                    logger.info("  [DRY RUN] Would execute Full Sync via Temp Engine")

            elif config['strategy'] == 'batch':
                start_date = args.start
                if not start_date:
                    last_wm = get_last_watermark(client, target_table)
                    if last_wm:
                        start_date = last_wm
                        logger.info(f"  Resuming from watermark: {start_date}")
                    else:
                        start_date = get_source_min_time(config)
                        logger.info(f"  No watermark. Auto-detected start: {start_date}")

                effective_step_days = config.get('step_days', args.step_days)
                effective_step_hours = config.get('step_hours', args.step_hours)
                batches = generate_batches(start_date, args.end, effective_step_days, effective_step_hours)
                logger.info(f"Generated {len(batches)} batches from {start_date} to {args.end}")

                session_total = 0
                session_total_duration = 0
                cached_min = None   # min 一旦查到就固定，後續批次只查 max
                for i, (start, end) in enumerate(batches, 1):
                    logger.info(f"Batch {i}/{len(batches)}: {start} -> {end}")
                    if not args.dry_run:
                        batch_count, batch_duration = sync_batch_adaptive(client, config, start, end)
                        session_total += batch_count
                        session_total_duration += batch_duration
                        row_count = session_total
                        min_dt, max_dt = query_data_min_max(
                            client, target_table, config.get('time_col'), known_min=cached_min
                        )
                        cached_min = min_dt or cached_min
                        update_watermark(client, target_table, end, session_total, session_total_duration, min_dt, max_dt)
                    else:
                        logger.info("  [DRY RUN] Would execute batch sync via Temp Engine")

        except Exception as e:
            logger.error(f"Stopping sync for {table_key} due to error: {e}")
            status = f"FAILED: {str(e)[:200]}"
        finally:
            duration = time.time() - start_t
            stats.append({
                "table": table_key,
                "duration": duration,
                "rows": row_count,
                "status": status
            })
            if not args.dry_run:
                # 連線已壞時這裡會拋例外；不擋下來會中斷迴圈並讓 summary 完全不印出
                try:
                    client.command(f"DROP TABLE IF EXISTS {temp_name}")
                except Exception as cleanup_err:
                    logger.warning(f"  Failed to drop temp ODBC table {temp_name}: {cleanup_err}")

    # Final Summary Report
    logger.info(f"\n{'='*60}")
    logger.info("FINAL SYNC SUMMARY")
    logger.info(f"{'Table':<35} | {'Duration':<10} | {'Rows':<10} | {'Status'}")
    logger.info("-" * 80)
    for s in stats:
        dur_str = f"{s['duration']:.2f}s"
        row_str = f"{s['rows']:,}"
        logger.info(f"{s['table']:<35} | {dur_str:>10} | {row_str:>10} | {s['status']}")
    logger.info("-" * 80)

    # Fail loud: 任何一張表 FAILED 就 exit 非 0，讓 wrapper(set -e)/排程真正顯示失敗，
    # 不再「全部失敗卻 exit 0、假裝 Complete」（masking bug）。
    failed = [s for s in stats if s["status"] != "SUCCESS"]
    if failed:
        logger.error(
            f"{len(failed)}/{len(stats)} table(s) FAILED: "
            + ", ".join(s["table"] for s in failed)
        )
        sys.exit(1)

    # Rebuild the derived MDM five-level dimension table from the freshly synced
    # bronze.common_mdm_* tables. Runs only after a clean full sync (see 'failed'
    # check above) so it never rebuilds from a partially-synced state, and only
    # for --table all since targeted single-table syncs don't touch MDM sources.
    if args.table == 'all' and not args.dry_run:
        dml_file = Path(__file__).resolve().parent.parent.parent / 'sql' / 'etl' / 'dml' / 'init_dim_mfg_five_level.sql'
        logger.info("Rebuilding silver.mv_dim_mfg_five_level from synced MDM tables...")
        execute_sql_file(client, dml_file, "MDM five-level dimension rebuild", force=True)

    logger.info("All operations completed.")

if __name__ == "__main__":
    main()
