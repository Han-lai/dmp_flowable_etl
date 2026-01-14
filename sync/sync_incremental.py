"""
Bronze 增量同步程式
支援增量同步（大表）和全量同步（小表）混合策略
"""

import time
import logging
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import clickhouse_connect

OUTPUT_DIR = "logs"

# ============================================
# 設定
# ============================================
CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# 增量同步表（大表，有追蹤欄位）
INCREMENTAL_TABLES = [
    {
        "source": "APP_SRV_BPM.dbo.ACT_HI_PROCINST",
        "target": "bronze.bpm_act_hi_procinst",
        "primary_key": "ID_",
        "tracking_col": "START_TIME_",  # 用 START_TIME_ 追蹤新建
    },
    {
        "source": "APP_SRV_BPM.dbo.ACT_HI_TASKINST",
        "target": "bronze.bpm_act_hi_taskinst",
        "primary_key": "ID_",
        "tracking_col": "LAST_UPDATED_TIME_",
    },
    {
        "source": "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK",
        "target": "bronze.bpm_act_hi_identitylink",
        "primary_key": "ID_",
        "tracking_col": "CREATE_TIME_",
    },
    {
        "source": "APP_SRV_BPM.dbo.ACT_HI_VARINST",
        "target": "bronze.bpm_act_hi_varinst",
        "primary_key": "ID_",
        "tracking_col": "LAST_UPDATED_TIME_",
    },
    {
        "source": "APP_SRV_COMMON.dbo.FlowableTaskStats",
        "target": "bronze.common_flowable_task_stats",
        "primary_key": "tuple()",  # 無主鍵，用 tuple()
        "tracking_col": "LastUpdatedTime",
        "allow_nullable_key": True,
    },
]

# 全量同步表（小表，無追蹤欄位或資料量小）
FULL_SYNC_TABLES = [
    {"source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF", "target": "bronze.bpm_act_re_procdef"},
    {"source": "APP_SRV_COMMON.dbo.HR_Employee", "target": "bronze.common_hr_employee"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleUserMapping", "target": "bronze.common_process_role_user_mapping"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleGroup", "target": "bronze.common_process_role_group"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleGroupMapping", "target": "bronze.common_process_role_group_mapping"},
    {"source": "APP_SRV_COMMON.dbo.EmpNodeRoleMapping", "target": "bronze.common_emp_node_role_mapping"},
    {"source": "APP_SRV_COMMON.dbo.EmpOrgInfoMapping", "target": "bronze.common_emp_org_info_mapping"},
    {"source": "APP_SRV_COMMON.dbo.EmpUserGroupMapping", "target": "bronze.common_emp_user_group_mapping"},
    {"source": "APP_SRV_COMMON.dbo.UserGroup", "target": "bronze.common_user_group"},
    {"source": "APP_SRV_COMMON.dbo.DMPFunctionConfig", "target": "bronze.common_dmp_function_config"},
    {"source": "APP_SRV_COMMON.dbo.DMPFunctionClientMapping", "target": "bronze.common_dmp_function_client_mapping"},
    {"source": "APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER", "target": "bronze.common_mdm_factory_area_master"},
    {"source": "APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER", "target": "bronze.common_mdm_mfg_plant_master"},
]

# ============================================
# Logging
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============================================
# 資料結構
# ============================================
@dataclass
class SyncResult:
    step: str
    duration_seconds: float
    row_count: Optional[int] = None
    status: str = "success"
    error: Optional[str] = None
    sync_type: str = "full"  # full or incremental

@dataclass
class SyncSummary:
    results: list = field(default_factory=list)
    total_duration: float = 0.0
    start_time: str = ""
    
    def add(self, result: SyncResult):
        self.results.append(result)
    
    def get_summary_text(self) -> str:
        lines = []
        lines.append("=" * 100)
        lines.append(f"同步結果 Summary - {self.start_time}")
        lines.append("=" * 100)
        lines.append(f"{'步驟':<45} {'類型':<12} {'耗時(秒)':<10} {'筆數':<12} {'狀態'}")
        lines.append("-" * 100)
        
        total_rows = 0
        for r in self.results:
            row_count = str(r.row_count) if r.row_count is not None else "-"
            lines.append(f"{r.step:<45} {r.sync_type:<12} {r.duration_seconds:<10.2f} {row_count:<12} {r.status}")
            if r.row_count:
                total_rows += r.row_count
        
        lines.append("-" * 100)
        lines.append(f"總耗時: {self.total_duration:.2f} 秒")
        lines.append(f"總筆數: {total_rows:,}")
        lines.append("=" * 100)
        return "\n".join(lines)
    
    def print_summary(self):
        print("\n" + self.get_summary_text())
    
    def save_to_file(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(OUTPUT_DIR, f"sync_incremental_{timestamp}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.get_summary_text())
        logger.info(f"結果已儲存到: {filepath}")

# ============================================
# 核心函數
# ============================================
def connect_clickhouse():
    logger.info(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client

def ensure_watermark_table(client):
    """建立 watermark 表（如果不存在）"""
    sql = """
    CREATE TABLE IF NOT EXISTS bronze._sync_watermark (
        table_name String,
        last_sync_time DateTime64(3),
        sync_time DateTime64(3),
        row_count UInt64
    ) ENGINE = ReplacingMergeTree(sync_time)
    ORDER BY (table_name)
    """
    client.command(sql)
    logger.info("Watermark 表已就緒")

def get_watermark(client, table_name: str) -> Optional[str]:
    """取得上次同步時間"""
    sql = f"""
    SELECT last_sync_time 
    FROM bronze._sync_watermark FINAL
    WHERE table_name = '{table_name}'
    """
    result = client.query(sql)
    if result.result_rows:
        return str(result.result_rows[0][0])
    return None

def update_watermark(client, table_name: str, last_sync_time: str, row_count: int):
    """更新 watermark"""
    sql = f"""
    INSERT INTO bronze._sync_watermark (table_name, last_sync_time, sync_time, row_count)
    VALUES ('{table_name}', '{last_sync_time}', now64(3), {row_count})
    """
    client.command(sql)

def check_table_exists(client, table_name: str) -> bool:
    """檢查表是否存在"""
    db, tbl = table_name.split(".")
    sql = f"EXISTS TABLE {table_name}"
    result = client.command(sql)
    return result == 1

def get_max_tracking_value(client, source: str, tracking_col: str) -> str:
    """從 MSSQL 取得最大追蹤欄位值"""
    sql = f"""
    SELECT * FROM jdbc('mssql_master', '
        SELECT MAX({tracking_col}) FROM {source}
    ')
    """
    result = client.query(sql)
    if result.result_rows and result.result_rows[0][0]:
        return str(result.result_rows[0][0])
    return None


def check_has_sync_time_column(client, table_name: str) -> bool:
    """檢查表是否有 _sync_time 欄位"""
    db, tbl = table_name.split(".")
    sql = f"""
    SELECT count(*) FROM system.columns 
    WHERE database = '{db}' AND table = '{tbl}' AND name = '_sync_time'
    """
    result = client.command(sql)
    return result > 0


def sync_incremental(client, config: dict) -> SyncResult:
    """增量同步單張表"""
    source = config["source"]
    target = config["target"]
    pk = config["primary_key"]
    tracking_col = config["tracking_col"]
    allow_nullable = config.get("allow_nullable_key", False)
    
    start = time.perf_counter()
    try:
        # 檢查目標表是否存在
        table_exists = check_table_exists(client, target)
        
        # 建立表的 SQL 模板
        settings = "SETTINGS allow_nullable_key = 1" if allow_nullable else ""
        
        if not table_exists:
            # 首次同步：建立表並全量載入
            logger.info(f"[{target}] 首次同步，建立表...")
            
            create_sql = f"""
            CREATE TABLE {target}
            ENGINE = ReplacingMergeTree(_sync_time)
            ORDER BY ({pk})
            {settings}
            AS SELECT *, now64(3) as _sync_time 
            FROM jdbc('mssql_master', 'SELECT * FROM {source}')
            """
            client.command(create_sql)
            
            row_count = client.command(f"SELECT count(*) FROM {target}")
            max_tracking = get_max_tracking_value(client, source, tracking_col)
            
            if max_tracking:
                update_watermark(client, target, max_tracking, row_count)
            
            duration = time.perf_counter() - start
            logger.info(f"[{target}] 首次同步完成，{row_count:,} 筆，耗時 {duration:.2f} 秒")
            return SyncResult(step=target, duration_seconds=duration, row_count=row_count, sync_type="initial")
        
        else:
            # 檢查是否有 _sync_time 欄位（舊表沒有）
            has_sync_time = check_has_sync_time_column(client, target)
            
            if not has_sync_time:
                # 舊表沒有 _sync_time，需要重建
                logger.info(f"[{target}] 舊表無 _sync_time 欄位，重建表...")
                
                # 備份舊表名
                backup_table = f"{target}_backup"
                client.command(f"DROP TABLE IF EXISTS {backup_table}")
                client.command(f"RENAME TABLE {target} TO {backup_table}")
                
                # 建立新表
                create_sql = f"""
                CREATE TABLE {target}
                ENGINE = ReplacingMergeTree(_sync_time)
                ORDER BY ({pk})
                {settings}
                AS SELECT *, now64(3) as _sync_time 
                FROM jdbc('mssql_master', 'SELECT * FROM {source}')
                """
                client.command(create_sql)
                
                # 刪除備份
                client.command(f"DROP TABLE IF EXISTS {backup_table}")
                
                row_count = client.command(f"SELECT count(*) FROM {target}")
                max_tracking = get_max_tracking_value(client, source, tracking_col)
                
                if max_tracking:
                    update_watermark(client, target, max_tracking, row_count)
                
                duration = time.perf_counter() - start
                logger.info(f"[{target}] 重建完成，{row_count:,} 筆，耗時 {duration:.2f} 秒")
                return SyncResult(step=target, duration_seconds=duration, row_count=row_count, sync_type="rebuild")
            
            # 增量同步
            watermark = get_watermark(client, target)
            
            if not watermark:
                # 沒有 watermark，取得目前最大值作為起點
                watermark = get_max_tracking_value(client, source, tracking_col)
                if watermark:
                    update_watermark(client, target, watermark, 0)
                logger.info(f"[{target}] 無 watermark，已設定初始值: {watermark}")
                duration = time.perf_counter() - start
                return SyncResult(step=target, duration_seconds=duration, row_count=0, sync_type="init_watermark")
            
            # 查詢增量資料並插入
            logger.info(f"[{target}] 增量同步，watermark: {watermark}")
            
            # 格式化 watermark（移除微秒後的多餘位數）
            watermark_formatted = watermark[:23] if len(watermark) > 23 else watermark
            
            insert_sql = f"""
            INSERT INTO {target}
            SELECT *, now64(3) as _sync_time
            FROM jdbc('mssql_master', '
                SELECT * FROM {source}
                WHERE {tracking_col} > CONVERT(datetime2, ''{watermark_formatted}'', 121)
            ')
            """
            client.command(insert_sql)
            
            # 計算新增筆數
            new_max = get_max_tracking_value(client, source, tracking_col)
            
            count_sql = f"""
            SELECT count(*) FROM jdbc('mssql_master', '
                SELECT 1 FROM {source}
                WHERE {tracking_col} > CONVERT(datetime2, ''{watermark_formatted}'', 121)
            ')
            """
            result = client.query(count_sql)
            row_count = result.result_rows[0][0] if result.result_rows else 0
            
            if new_max and new_max > watermark:
                update_watermark(client, target, new_max, row_count)
            
            duration = time.perf_counter() - start
            logger.info(f"[{target}] 增量同步完成，{row_count:,} 筆，耗時 {duration:.2f} 秒")
            return SyncResult(step=target, duration_seconds=duration, row_count=row_count, sync_type="incremental")
    
    except Exception as e:
        duration = time.perf_counter() - start
        logger.error(f"[{target}] 同步失敗: {e}")
        return SyncResult(step=target, duration_seconds=duration, status="failed", error=str(e), sync_type="incremental")


def sync_full(client, config: dict) -> SyncResult:
    """全量同步單張表（DROP + CREATE）"""
    source = config["source"]
    target = config["target"]
    
    start = time.perf_counter()
    try:
        client.command(f"DROP TABLE IF EXISTS {target}")
        
        sql = f"""
        CREATE TABLE {target} 
        ENGINE = MergeTree() 
        ORDER BY tuple() 
        AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM {source}')
        """
        client.command(sql)
        
        row_count = client.command(f"SELECT count(*) FROM {target}")
        
        duration = time.perf_counter() - start
        logger.info(f"[{target}] 全量同步完成，{row_count:,} 筆，耗時 {duration:.2f} 秒")
        return SyncResult(step=target, duration_seconds=duration, row_count=row_count, sync_type="full")
    
    except Exception as e:
        duration = time.perf_counter() - start
        logger.error(f"[{target}] 同步失敗: {e}")
        return SyncResult(step=target, duration_seconds=duration, status="failed", error=str(e), sync_type="full")


def run_sync(mode: str = "all"):
    """
    執行同步
    mode: 
        - "all": 全部同步（增量+全量）
        - "incremental": 只同步增量表
        - "full": 只同步全量表
    """
    summary = SyncSummary()
    summary.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_start = time.perf_counter()
    
    client = connect_clickhouse()
    
    # 確保 watermark 表存在
    ensure_watermark_table(client)
    
    # 增量同步
    if mode in ["all", "incremental"]:
        logger.info("=" * 50)
        logger.info("開始增量同步...")
        logger.info("=" * 50)
        for config in INCREMENTAL_TABLES:
            result = sync_incremental(client, config)
            summary.add(result)
    
    # 全量同步
    if mode in ["all", "full"]:
        logger.info("=" * 50)
        logger.info("開始全量同步...")
        logger.info("=" * 50)
        for config in FULL_SYNC_TABLES:
            result = sync_full(client, config)
            summary.add(result)
    
    summary.total_duration = time.perf_counter() - total_start
    summary.print_summary()
    summary.save_to_file()
    
    return summary


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    run_sync(mode)
