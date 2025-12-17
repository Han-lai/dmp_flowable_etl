"""
MSSQL → ClickHouse 資料同步程式
使用 Python 主動控制 DDL/DML，並記錄執行時間
"""

import time
import logging
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import clickhouse_connect

# 輸出目錄
OUTPUT_DIR = "logs"

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
# 全部使用 tuple() 避免 Nullable 欄位問題
TABLES_TO_SYNC = [
    # APP_SRV_BPM
    {"source": "APP_SRV_BPM.dbo.ACT_HI_PROCINST", "target": "bronze.bpm_act_hi_procinst", "order_by": "tuple()"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_TASKINST", "target": "bronze.bpm_act_hi_taskinst", "order_by": "tuple()"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK", "target": "bronze.bpm_act_hi_identitylink", "order_by": "tuple()"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_VARINST", "target": "bronze.bpm_act_hi_varinst", "order_by": "tuple()"},
    {"source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF", "target": "bronze.bpm_act_re_procdef", "order_by": "tuple()"},
    # APP_SRV_COMMON
    {"source": "APP_SRV_COMMON.dbo.FlowableTaskStats", "target": "bronze.common_flowable_task_stats", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.HR_Employee", "target": "bronze.common_hr_employee", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleUserMapping", "target": "bronze.common_process_role_user_mapping", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleGroup", "target": "bronze.common_process_role_group", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.ProcessRoleGroupMapping", "target": "bronze.common_process_role_group_mapping", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.EmpNodeRoleMapping", "target": "bronze.common_emp_node_role_mapping", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.EmpOrgInfoMapping", "target": "bronze.common_emp_org_info_mapping", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.EmpUserGroupMapping", "target": "bronze.common_emp_user_group_mapping", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.UserGroup", "target": "bronze.common_user_group", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.DMPFunctionConfig", "target": "bronze.common_dmp_function_config", "order_by": "tuple()"},
    {"source": "APP_SRV_COMMON.dbo.DMPFunctionClientMapping", "target": "bronze.common_dmp_function_client_mapping", "order_by": "tuple()"},
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
    start_time: str = ""
    
    def add(self, result: TimingResult):
        self.results.append(result)
    
    def get_summary_text(self) -> str:
        """產生 summary 文字"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"同步結果 Summary - {self.start_time}")
        lines.append("=" * 80)
        lines.append(f"{'步驟':<50} {'耗時(秒)':<10} {'筆數':<12} {'狀態'}")
        lines.append("-" * 80)
        
        total_rows = 0
        success_count = 0
        failed_count = 0
        
        for r in self.results:
            row_count = str(r.row_count) if r.row_count is not None else "-"
            lines.append(f"{r.step:<50} {r.duration_seconds:<10.2f} {row_count:<12} {r.status}")
            if r.row_count:
                total_rows += r.row_count
            if r.status == "success":
                success_count += 1
            else:
                failed_count += 1
        
        lines.append("-" * 80)
        lines.append(f"{'總耗時':<50} {self.total_duration:<10.2f}")
        lines.append(f"{'總筆數':<50} {'':<10} {total_rows:,}")
        lines.append(f"{'成功/失敗':<50} {'':<10} {success_count}/{failed_count}")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def print_summary(self):
        """輸出到 console"""
        print("\n" + self.get_summary_text())
    
    def save_to_file(self, output_dir: str = OUTPUT_DIR):
        """儲存到檔案"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sync_result_{timestamp}.txt"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.get_summary_text())
            f.write("\n\n")
            
            # 寫入失敗詳情
            failed = [r for r in self.results if r.status == "failed"]
            if failed:
                f.write("=" * 80 + "\n")
                f.write("失敗詳情\n")
                f.write("=" * 80 + "\n")
                for r in failed:
                    f.write(f"\n{r.step}:\n")
                    f.write(f"  Error: {r.error}\n")
        
        logger.info(f"結果已儲存到: {filepath}")
        return filepath

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
        
        # CREATE TABLE AS SELECT（透過 JDBC Bridge）- 單行避免格式問題
        sql = f"CREATE TABLE {target} ENGINE = MergeTree() ORDER BY {order_by} AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM {source}')"
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
    summary.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    
    # 5. 輸出 summary 到 console 和檔案
    summary.print_summary()
    summary.save_to_file()
    
    return summary

# ============================================
# 主程式
# ============================================
if __name__ == "__main__":
    run_sync()
