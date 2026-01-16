"""
資料同步驗證程式
比對 MSSQL 與 ClickHouse 的資料筆數和品質
"""

import os
from datetime import datetime
from dataclasses import dataclass
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

OUTPUT_DIR = "logs"

# 表對應關係（MSSQL 來源 → ClickHouse 目標）
TABLE_MAPPINGS = [
    {"source": "APP_SRV_BPM.dbo.ACT_HI_PROCINST", "target": "bronze.bpm_act_hi_procinst"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_TASKINST", "target": "bronze.bpm_act_hi_taskinst"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK", "target": "bronze.bpm_act_hi_identitylink"},
    {"source": "APP_SRV_BPM.dbo.ACT_HI_VARINST", "target": "bronze.bpm_act_hi_varinst"},
    {"source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF", "target": "bronze.bpm_act_re_procdef"},
    {"source": "APP_SRV_COMMON.dbo.FlowableTaskStats", "target": "bronze.common_flowable_task_stats"},
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
]

# ============================================
# 資料結構
# ============================================
@dataclass
class RowCountResult:
    source_table: str
    target_table: str
    source_count: int
    target_count: int
    diff: int
    diff_pct: float
    status: str  # PASS, WARN, FAIL
    error: Optional[str] = None


# ============================================
# 核心函數
# ============================================
def connect_clickhouse():
    """建立 ClickHouse 連線"""
    print(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    print("ClickHouse 連線成功")
    return client


def get_source_count(client, source_table: str) -> int:
    """從 MSSQL 取得資料筆數（透過 JDBC Bridge）"""
    sql = f"SELECT * FROM jdbc('mssql_master', 'SELECT COUNT(*) as cnt FROM {source_table}')"
    result = client.query(sql)
    return result.result_rows[0][0]


def get_target_count(client, target_table: str) -> int:
    """從 ClickHouse 取得資料筆數"""
    sql = f"SELECT count(*) FROM {target_table}"
    return client.command(sql)


def validate_row_counts(client) -> list:
    """驗證所有表的 row count"""
    results = []
    
    for mapping in TABLE_MAPPINGS:
        source = mapping["source"]
        target = mapping["target"]
        
        try:
            source_count = get_source_count(client, source)
            target_count = get_target_count(client, target)
            diff = target_count - source_count
            diff_pct = (diff / source_count * 100) if source_count > 0 else 0
            
            # 判斷狀態
            if abs(diff_pct) < 0.1:
                status = "PASS"
            elif abs(diff_pct) < 1.0:
                status = "WARN"
            else:
                status = "FAIL"
            
            result = RowCountResult(
                source_table=source,
                target_table=target,
                source_count=source_count,
                target_count=target_count,
                diff=diff,
                diff_pct=diff_pct,
                status=status
            )
            print(f"  {target}: {source_count:,} → {target_count:,} ({status})")
            
        except Exception as e:
            result = RowCountResult(
                source_table=source,
                target_table=target,
                source_count=0,
                target_count=0,
                diff=0,
                diff_pct=0,
                status="ERROR",
                error=str(e)
            )
            print(f"  {target}: ERROR - {e}")
        
        results.append(result)
    
    return results


def generate_report(results: list) -> str:
    """產生驗證報告"""
    lines = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines.append("=" * 100)
    lines.append(f"資料同步驗證報告 - {timestamp}")
    lines.append("=" * 100)
    lines.append("")
    
    # Row Count 比對
    lines.append("## Row Count 比對")
    lines.append("-" * 100)
    lines.append(f"{'來源表':<45} {'MSSQL':<12} {'ClickHouse':<12} {'差異':<10} {'差異%':<8} {'狀態'}")
    lines.append("-" * 100)
    
    total_source = 0
    total_target = 0
    pass_count = 0
    warn_count = 0
    fail_count = 0
    error_count = 0
    
    for r in results:
        total_source += r.source_count
        total_target += r.target_count
        
        if r.status == "PASS":
            pass_count += 1
        elif r.status == "WARN":
            warn_count += 1
        elif r.status == "FAIL":
            fail_count += 1
        else:
            error_count += 1
        
        source_name = r.source_table.split(".")[-1]
        lines.append(f"{source_name:<45} {r.source_count:<12,} {r.target_count:<12,} {r.diff:<10,} {r.diff_pct:<8.2f}% {r.status}")
    
    lines.append("-" * 100)
    total_diff = total_target - total_source
    total_diff_pct = (total_diff / total_source * 100) if total_source > 0 else 0
    lines.append(f"{'總計':<45} {total_source:<12,} {total_target:<12,} {total_diff:<10,} {total_diff_pct:<8.2f}%")
    lines.append("")
    
    # 摘要
    lines.append("## 驗證摘要")
    lines.append("-" * 50)
    lines.append(f"總表數：{len(results)}")
    lines.append(f"PASS（差異 < 0.1%）：{pass_count}")
    lines.append(f"WARN（差異 0.1% - 1%）：{warn_count}")
    lines.append(f"FAIL（差異 > 1%）：{fail_count}")
    lines.append(f"ERROR：{error_count}")
    lines.append("")
    
    # 錯誤詳情
    errors = [r for r in results if r.error]
    if errors:
        lines.append("## 錯誤詳情")
        lines.append("-" * 50)
        for r in errors:
            lines.append(f"{r.target_table}: {r.error}")
        lines.append("")
    
    lines.append("=" * 100)
    
    return "\n".join(lines)


def save_report(report: str):
    """儲存報告到檔案"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"validation_report_{timestamp}.txt"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n報告已儲存到: {filepath}")
    return filepath


def run_validation():
    """執行完整驗證流程"""
    print("=" * 60)
    print("開始資料同步驗證")
    print("=" * 60)
    
    # 1. 連線
    client = connect_clickhouse()
    
    # 2. Row Count 驗證
    print("\n[1/2] Row Count 比對...")
    results = validate_row_counts(client)
    
    # 3. 產生報告
    print("\n[2/2] 產生驗證報告...")
    report = generate_report(results)
    
    # 4. 輸出報告
    print(report)
    save_report(report)
    
    return results


# ============================================
# 主程式
# ============================================
if __name__ == "__main__":
    run_validation()
