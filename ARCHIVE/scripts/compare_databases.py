"""
ClickHouse Database 比較工具
比較 bronze (JDBC Bridge) 與 default (Airbyte) 的資料
"""

import time
import logging
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict
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

# 表對應關係 (bronze 表名 → default 表名)
TABLE_MAPPINGS = [
    {"bronze": "bronze.bpm_act_hi_identitylink", "default": "default.ACT_HI_IDENTITYLINK"},
    {"bronze": "bronze.bpm_act_hi_procinst", "default": "default.ACT_HI_PROCINST"},
    {"bronze": "bronze.bpm_act_hi_taskinst", "default": "default.ACT_HI_TASKINST"},
    {"bronze": "bronze.bpm_act_hi_varinst", "default": "default.ACT_HI_VARINST"},
    {"bronze": "bronze.bpm_act_re_procdef", "default": "default.ACT_RE_PROCDEF"},
    {"bronze": "bronze.common_dmp_function_client_mapping", "default": "default.DMPFunctionClientMapping"},
    {"bronze": "bronze.common_dmp_function_config", "default": "default.DMPFunctionConfig"},
    {"bronze": "bronze.common_emp_node_role_mapping", "default": "default.EmpNodeRoleMapping"},
    {"bronze": "bronze.common_emp_org_info_mapping", "default": "default.EmpOrgInfoMapping"},
    {"bronze": "bronze.common_emp_user_group_mapping", "default": "default.EmpUserGroupMapping"},
    {"bronze": "bronze.common_flowable_task_stats", "default": "default.FlowableTaskStats"},
    {"bronze": "bronze.common_hr_employee", "default": "default.HR_Employee"},
    {"bronze": "bronze.common_process_role_group", "default": "default.ProcessRoleGroup"},
    {"bronze": "bronze.common_process_role_group_mapping", "default": "default.ProcessRoleGroupMapping"},
    {"bronze": "bronze.common_process_role_user_mapping", "default": "default.ProcessRoleUserMapping"},
    {"bronze": "bronze.common_user_group", "default": "default.UserGroup"},
]

# ============================================
# SQL 查詢
# ============================================
SQL_ROW_COUNT = "SELECT count(*) FROM {table}"

SQL_TABLE_SIZE = """
SELECT 
    formatReadableSize(sum(bytes_on_disk)) as size,
    sum(bytes_on_disk) as bytes
FROM system.parts 
WHERE database = '{db}' AND table = '{table}' AND active = 1
"""

SQL_SCHEMA = """
SELECT name, type 
FROM system.columns 
WHERE database = '{db}' AND table = '{table}'
ORDER BY position
"""

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
# 資料結構
# ============================================
@dataclass
class CompareResult:
    bronze_table: str
    default_table: str
    bronze_rows: int = 0
    default_rows: int = 0
    row_diff: int = 0
    bronze_size: str = "-"
    default_size: str = "-"
    bronze_columns: int = 0
    default_columns: int = 0
    extra_columns: List[str] = field(default_factory=list)
    status: str = "success"
    error: Optional[str] = None

@dataclass
class CompareSummary:
    results: List[CompareResult] = field(default_factory=list)
    total_duration: float = 0.0
    start_time: str = ""
    
    def add(self, result: CompareResult):
        self.results.append(result)
    
    def get_summary_text(self) -> str:
        lines = []
        lines.append("=" * 120)
        lines.append(f"Database 比較結果 - {self.start_time}")
        lines.append("bronze (JDBC Bridge) vs default (Airbyte)")
        lines.append("=" * 120)
        
        # Row Count 比較
        lines.append("\n【1. Row Count 比較】")
        lines.append("-" * 100)
        lines.append(f"{'Bronze Table':<45} {'Default Table':<45} {'Bronze':<12} {'Default':<12} {'Diff'}")
        lines.append("-" * 100)
        for r in self.results:
            if r.status == "success":
                lines.append(f"{r.bronze_table:<45} {r.default_table:<45} {r.bronze_rows:<12,} {r.default_rows:<12,} {r.row_diff:+,}")
            else:
                lines.append(f"{r.bronze_table:<45} {r.default_table:<45} {'ERROR':<12} {'ERROR':<12} -")
        
        # Size 比較
        lines.append("\n【2. 資料大小比較】")
        lines.append("-" * 100)
        lines.append(f"{'Bronze Table':<45} {'Default Table':<45} {'Bronze Size':<15} {'Default Size'}")
        lines.append("-" * 100)
        for r in self.results:
            if r.status == "success":
                lines.append(f"{r.bronze_table:<45} {r.default_table:<45} {r.bronze_size:<15} {r.default_size}")
        
        # Schema 比較
        lines.append("\n【3. Schema 比較 (欄位數)】")
        lines.append("-" * 100)
        lines.append(f"{'Bronze Table':<45} {'Default Table':<45} {'Bronze':<10} {'Default':<10} {'Extra (Airbyte)'}")
        lines.append("-" * 100)
        for r in self.results:
            if r.status == "success":
                extra = ", ".join(r.extra_columns[:5])
                if len(r.extra_columns) > 5:
                    extra += f" (+{len(r.extra_columns)-5} more)"
                lines.append(f"{r.bronze_table:<45} {r.default_table:<45} {r.bronze_columns:<10} {r.default_columns:<10} {extra}")
        
        # 統計
        lines.append("\n" + "=" * 120)
        success = sum(1 for r in self.results if r.status == "success")
        failed = sum(1 for r in self.results if r.status == "failed")
        lines.append(f"總耗時: {self.total_duration:.2f} 秒")
        lines.append(f"比較表數: {len(self.results)} (成功: {success}, 失敗: {failed})")
        lines.append("=" * 120)
        
        return "\n".join(lines)
    
    def print_summary(self):
        print("\n" + self.get_summary_text())
    
    def save_to_file(self, output_dir: str = OUTPUT_DIR):
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"compare_result_{timestamp}.txt"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.get_summary_text())
        
        logger.info(f"結果已儲存到: {filepath}")
        return filepath

# ============================================
# 核心函數
# ============================================
def connect_clickhouse():
    logger.info(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client

def parse_table_name(full_name: str) -> tuple:
    """解析 database.table 格式"""
    parts = full_name.split(".")
    return parts[0], parts[1]

def get_row_count(client, table: str) -> int:
    try:
        return client.command(SQL_ROW_COUNT.format(table=table))
    except:
        return 0

def get_table_size(client, db: str, table: str) -> str:
    try:
        result = client.query(SQL_TABLE_SIZE.format(db=db, table=table))
        if result.result_rows:
            return result.result_rows[0][0]
        return "-"
    except:
        return "-"

def get_columns(client, db: str, table: str) -> List[str]:
    try:
        result = client.query(SQL_SCHEMA.format(db=db, table=table))
        return [row[0] for row in result.result_rows]
    except:
        return []

def compare_table(client, mapping: dict) -> CompareResult:
    bronze_full = mapping["bronze"]
    default_full = mapping["default"]
    
    result = CompareResult(bronze_table=bronze_full, default_table=default_full)
    
    try:
        bronze_db, bronze_table = parse_table_name(bronze_full)
        default_db, default_table = parse_table_name(default_full)
        
        # Row count
        result.bronze_rows = get_row_count(client, bronze_full)
        result.default_rows = get_row_count(client, default_full)
        result.row_diff = result.default_rows - result.bronze_rows
        
        # Size
        result.bronze_size = get_table_size(client, bronze_db, bronze_table)
        result.default_size = get_table_size(client, default_db, default_table)
        
        # Schema
        bronze_cols = get_columns(client, bronze_db, bronze_table)
        default_cols = get_columns(client, default_db, default_table)
        result.bronze_columns = len(bronze_cols)
        result.default_columns = len(default_cols)
        result.extra_columns = [c for c in default_cols if c not in bronze_cols]
        
        logger.info(f"比較完成: {bronze_full} vs {default_full}")
        
    except Exception as e:
        result.status = "failed"
        result.error = str(e)
        logger.error(f"比較失敗 {bronze_full}: {e}")
    
    return result

def run_compare():
    summary = CompareSummary()
    summary.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_start = time.perf_counter()
    
    client = connect_clickhouse()
    
    for mapping in TABLE_MAPPINGS:
        result = compare_table(client, mapping)
        summary.add(result)
    
    summary.total_duration = time.perf_counter() - total_start
    summary.print_summary()
    summary.save_to_file()
    
    return summary

if __name__ == "__main__":
    run_compare()
