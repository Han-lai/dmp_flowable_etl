"""
MSSQL → ClickHouse 資料同步程式
使用 Python 主動控制 DDL/DML，並記錄執行時間
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional
import clickhouse_connect

# ============================================
# 設定
# ============================================
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# 要同步的表（MSSQL 來源 → ClickHouse 目標）
# 使用 tuple() 包裝避免 Nullable 問題，或使用非 Nullable 欄位
TABLES_TO_SYNC = [
    # APP_SRV_BPM
    {"source": "APP_SRV_BPM.dbo.ACT_HI_PROCINST", "target": "bronze.bpm_act_hi_procinst", "order_by": "ID_"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_TASKINST", "target": "bronze.bpm_act_hi_taskinst", "order_by": "ID_"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK", "target": "bronze.bpm_act_hi_identitylink", "order_by": "ID_"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_VARINST", "target": "bronze.bpm_act_hi_varinst", "order_by": "ID_"},
    {"source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF", "target": "bronze.bpm_act_re_procdef", "order_by": "ID_"},
    # APP_SRV_COMMON
    {"source": "APP_SRV_COMMON.dbo.FlowableTaskStats", "target": "bronze.common_flowable_task_stats", "order_by": "Id"},
    {"source": "APP_SRV_COMMON.dbo.HR_Employee", "target": "bronze.common_hr_employee", "order_by": "EmpCode"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleUserMapping", "target": "bronze.common_process_role_user_mapping", "order_by": "Id"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleGroup", "target": "bronze.common_process_role_group", "order_by": "GroupCode"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleGroupMapping", "target": "bronze.common_process_role_group_mapping", "order_by": "Id"},
    {"source": "APP_SRV_COMMON.dbo.EmpNodeRoleMapping", "target": "bronze.common_emp_node_role_mapping", "order_by": "Id"},
    {"source": "APP_SRV_COMMON.dbo.EmpOrgInfoMapping", "target": "bronze.common_emp_org_info_mapping", "order_by": "Id"},
    {"source": "APP_SRV_COMMON.dbo.EmpUserGroupMapping", "target": "bronze.common_emp_user_group_mapping", "order_by": "Id"},
    {"source": "APP_SRV_COMMON.dbo.UserGroup", "target": "bronze.common_user_group", "order_by": "Id"},
    {"source": "APP_SRV_COMMON.dbo.DMPFunctionConfig", "target": "bronze.common_dmp_function_config", "order_by": "Id"},
    {"source": "APP_SRV_COMMON.dbo.DMPFunctionClientMapping", "target": "bronze.common_dmp_function_client_mapping", "order_by": "Id"},
]

# ============================================
# Logging 設定
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============================================
# 時間記錄
# ============================================
@dataclass
class TimingResult:
    step: str
    duration_seconds: float
    row_count: Optional[int] = None
    status: str = "success"
    error: Optional[str] = None

@dataclass
class SyncSummary:
    results: list = field(default_factory=list)
    total_duration: float = 0.0
    
    def add(self, result: TimingResult):
        self.results.append(result)
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print("同步結果 Summary")
        print("=" * 60)
        print(f"{'步驟':<45} {'耗時(秒)':<10} {'筆數':<10} {'狀態'}")
        print("-" * 60)
        for r in self.results:
            row_count = str(r.row_count) if r.row_count is not None else "-"
            print(f"{r.step:<45} {r.duration_seconds:<10.2f} {row_count:<10} {r.status}")
        print("-" * 60)
        print(f"{'總耗時':<45} {self.total_duration:<10.2f}")
        print("=" * 60)

# ============================================
# 核心函數
# ============================================
def connect_clickhouse() -> clickhouse_connect.driver.Client:
    """建立 ClickHouse 連線"""
    logger.info(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    # 測試連線
    result = client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client

def create_database(client: clickhouse_connect.driver.Client) -> TimingResult:
    """建立 bronze database"""
    start = time.perf_counter()
    try:
        client.command("CREATE DATABASE IF NOT EXISTS bronze")
        duration = time.perf_counter() - start
        logger.info(f"建立 database 'bronze' 完成，耗時 {duration:.2f} 秒")
        return TimingResult(step="CREATE DATABASE bronze", duration_seconds=duration)
    except Exception as e:
        duration = time.perf_counter() - start
        logger.error(f"建立 database 失敗: {e}")
        return TimingResult(step="CREATE DATABASE bronze", duration_seconds=duration, status="failed", error=str(e))

def sync_table(client: clickhouse_connect.driver.Client, table_config: dict) -> TimingResult:
    """同步單張表（DROP + CREATE TABLE AS SELECT）"""
    source = table_config["source"]
    target = table_config["target"]
    order_by = table_config["order_by"]
    
    start = time.perf_counter()
    try:
        # DROP TABLE IF EXISTS
        client.command(f"DROP TABLE IF EXISTS {target}")
        
        # CREATE TABLE AS SELECT（透過 JDBC Bridge）
        sql = f"""
        CREATE TABLE {target}
        ENGINE = MergeTree()
        ORDER BY {order_by}
        AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM {source}')
        """
        client.command(sql)
        
        # 取得 row count
        row_count = client.command(f"SELECT count(*) FROM {target}")
        
        duration = time.perf_counter() - start
        logger.info(f"同步 {target} 完成，{row_count:,} 筆，耗時 {duration:.2f} 秒")
        return TimingResult(step=f"SYNC {target}", duration_seconds=duration, row_count=row_count)
    
    except Exception as e:
        duration = time.perf_counter() - start
        logger.error(f"同步 {target} 失敗: {e}")
        return TimingResult(step=f"SYNC {target}", duration_seconds=duration, status="failed", error=str(e))

def run_sync():
    """執行完整同步流程"""
    summary = SyncSummary()
    total_start = time.perf_counter()
    
    # 1. 連線
    client = connect_clickhouse()
    
    # 2. 建立 database
    result = create_database(client)
    summary.add(result)
    
    # 3. 同步所有表
    for table_config in TABLES_TO_SYNC:
        result = sync_table(client, table_config)
        summary.add(result)
    
    # 4. 計算總耗時
    summary.total_duration = time.perf_counter() - total_start
    
    # 5. 輸出 summary
    summary.print_summary()
    
    return summary

# ============================================
# 主程式
# ============================================
if __name__ == "__main__":
    run_sync()
