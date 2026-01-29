#!/usr/bin/env python3
"""
資料完整性驗證腳本
驗證 MSSQL 與 ClickHouse 之間的資料一致性
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
import clickhouse_connect

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# 要驗證的表格
VALIDATION_TABLES = [
    {
        "mssql_source": "APP_SRV_BPM.dbo.ACT_HI_PROCINST",
        "clickhouse_target": "bronze.bpm_act_hi_procinst",
        "description": "流程實例歷史"
    },
    {
        "mssql_source": "APP_SRV_BPM.dbo.ACT_HI_TASKINST",
        "clickhouse_target": "bronze.bpm_act_hi_taskinst", 
        "description": "任務實例歷史"
    },
    {
        "mssql_source": "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK",
        "clickhouse_target": "bronze.bpm_act_hi_identitylink",
        "description": "身份連結歷史"
    },
    {
        "mssql_source": "APP_SRV_BPM.dbo.ACT_HI_VARINST",
        "clickhouse_target": "bronze.bmp_act_hi_varinst",
        "description": "變數實例歷史"
    },
    {
        "mssql_source": "APP_SRV_COMMON.dbo.FlowableTaskStats",
        "clickhouse_target": "bronze.common_flowable_task_stats",
        "description": "任務統計"
    },
    {
        "mssql_source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF",
        "clickhouse_target": "bronze.bpm_act_re_procdef",
        "description": "流程定義"
    },
    {
        "mssql_source": "APP_SRV_COMMON.dbo.HR_Employee",
        "clickhouse_target": "bronze.common_hr_employee",
        "description": "員工資料"
    }
]

class ValidationResult:
    def __init__(self):
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
    
    def add_result(self, table_name, test_type, status, mssql_count=None, clickhouse_count=None, message=""):
        self.results.append({
            "table": table_name,
            "test": test_type,
            "status": status,
            "mssql_count": mssql_count,
            "clickhouse_count": clickhouse_count,
            "message": message
        })
        
        self.total_tests += 1
        if status == "PASS":
            self.passed_tests += 1
        else:
            self.failed_tests += 1
    
    def print_summary(self):
        print("\n" + "=" * 100)
        print("資料完整性驗證結果")
        print("=" * 100)
        print(f"{'表格':<35} {'測試項目':<15} {'MSSQL筆數':<12} {'ClickHouse筆數':<15} {'狀態':<8} {'訊息'}")
        print("-" * 100)
        
        for result in self.results:
            mssql_str = f"{result['mssql_count']:,}" if result['mssql_count'] is not None else "-"
            ch_str = f"{result['clickhouse_count']:,}" if result['clickhouse_count'] is not None else "-"
            status_icon = "✅" if result['status'] == "PASS" else "❌"
            
            print(f"{result['table']:<35} {result['test']:<15} {mssql_str:<12} {ch_str:<15} {status_icon:<8} {result['message']}")
        
        print("-" * 100)
        print(f"總計測試: {self.total_tests}")
        print(f"通過: {self.passed_tests}")
        print(f"失敗: {self.failed_tests}")
        print(f"成功率: {(self.passed_tests/self.total_tests*100):.1f}%")
        print("=" * 100)
        
        if self.failed_tests == 0:
            print("🎉 所有資料完整性驗證都通過了！")
        else:
            print("⚠️ 有部分驗證失敗，請檢查資料同步狀態")
    
    def save_to_file(self):
        """儲存結果到檔案"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/data_integrity_validation_{timestamp}.txt"
        
        os.makedirs("logs", exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write("資料完整性驗證結果\n")
            f.write("=" * 100 + "\n")
            f.write(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"總計測試: {self.total_tests}\n")
            f.write(f"通過: {self.passed_tests}\n") 
            f.write(f"失敗: {self.failed_tests}\n")
            f.write(f"成功率: {(self.passed_tests/self.total_tests*100):.1f}%\n")
            f.write("=" * 100 + "\n\n")
            
            for result in self.results:
                f.write(f"表格: {result['table']}\n")
                f.write(f"測試: {result['test']}\n")
                f.write(f"狀態: {result['status']}\n")
                if result['mssql_count'] is not None:
                    f.write(f"MSSQL 筆數: {result['mssql_count']:,}\n")
                if result['clickhouse_count'] is not None:
                    f.write(f"ClickHouse 筆數: {result['clickhouse_count']:,}\n")
                if result['message']:
                    f.write(f"訊息: {result['message']}\n")
                f.write("-" * 50 + "\n")
        
        logger.info(f"驗證結果已儲存到: {filename}")
        return filename

def connect_clickhouse():
    """建立 ClickHouse 連線"""
    logger.info(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client

def get_mssql_count(client, table_name):
    """取得 MSSQL 表格筆數"""
    try:
        sql = f"SELECT * FROM jdbc('mssql_master', 'SELECT COUNT(*) as cnt FROM {table_name}')"
        result = client.query(sql)
        return result.result_rows[0][0] if result.result_rows else 0
    except Exception as e:
        logger.error(f"查詢 MSSQL 表格 {table_name} 失敗: {e}")
        return None

def get_clickhouse_count(client, table_name):
    """取得 ClickHouse 表格筆數"""
    try:
        sql = f"SELECT count(*) FROM {table_name}"
        return client.command(sql)
    except Exception as e:
        logger.error(f"查詢 ClickHouse 表格 {table_name} 失敗: {e}")
        return None

def check_table_exists(client, table_name):
    """檢查 ClickHouse 表格是否存在"""
    try:
        sql = f"EXISTS TABLE {table_name}"
        return client.command(sql) == 1
    except Exception:
        return False

def validate_table_counts(client, validation_config):
    """驗證單張表的筆數一致性"""
    mssql_source = validation_config["mssql_source"]
    clickhouse_target = validation_config["clickhouse_target"]
    description = validation_config["description"]
    
    logger.info(f"驗證表格: {clickhouse_target} ({description})")
    
    result = ValidationResult()
    
    # 檢查 ClickHouse 表格是否存在
    if not check_table_exists(client, clickhouse_target):
        result.add_result(
            clickhouse_target, 
            "表格存在性", 
            "FAIL", 
            message="ClickHouse 表格不存在"
        )
        return result
    
    result.add_result(clickhouse_target, "表格存在性", "PASS")
    
    # 取得筆數
    mssql_count = get_mssql_count(client, mssql_source)
    clickhouse_count = get_clickhouse_count(client, clickhouse_target)
    
    if mssql_count is None:
        result.add_result(
            clickhouse_target,
            "MSSQL 查詢",
            "FAIL",
            message="無法查詢 MSSQL 資料"
        )
        return result
    
    if clickhouse_count is None:
        result.add_result(
            clickhouse_target,
            "ClickHouse 查詢", 
            "FAIL",
            message="無法查詢 ClickHouse 資料"
        )
        return result
    
    # 比較筆數
    if mssql_count == clickhouse_count:
        result.add_result(
            clickhouse_target,
            "筆數一致性",
            "PASS",
            mssql_count,
            clickhouse_count
        )
    else:
        diff = clickhouse_count - mssql_count
        result.add_result(
            clickhouse_target,
            "筆數一致性",
            "FAIL", 
            mssql_count,
            clickhouse_count,
            f"差異: {diff:+,}"
        )
    
    return result

def validate_sync_freshness(client):
    """驗證同步新鮮度"""
    logger.info("驗證同步新鮮度...")
    
    result = ValidationResult()
    
    try:
        # 檢查 watermark 表
        if not check_table_exists(client, "bronze._sync_watermark"):
            result.add_result("系統", "Watermark表", "FAIL", message="Watermark 表不存在")
            return result
        
        # 查詢最近同步時間
        sql = """
        SELECT 
            table_name,
            last_sync_time,
            sync_time,
            now() - sync_time as hours_since_sync
        FROM bronze._sync_watermark FINAL
        ORDER BY sync_time DESC
        """
        
        watermark_result = client.query(sql)
        
        if not watermark_result.result_rows:
            result.add_result("系統", "同步記錄", "FAIL", message="無同步記錄")
            return result
        
        # 檢查是否有超過 24 小時未同步的表
        stale_tables = []
        for row in watermark_result.result_rows:
            table_name, last_sync, sync_time, hours_since = row
            if hours_since > 24:  # 超過 24 小時
                stale_tables.append(f"{table_name} ({hours_since:.1f}h)")
        
        if stale_tables:
            result.add_result(
                "系統",
                "同步新鮮度", 
                "FAIL",
                message=f"過期表格: {', '.join(stale_tables)}"
            )
        else:
            result.add_result("系統", "同步新鮮度", "PASS", message="所有表格同步正常")
            
    except Exception as e:
        result.add_result("系統", "同步新鮮度", "FAIL", message=str(e))
    
    return result

def main():
    """主程式"""
    logger.info("=" * 80)
    logger.info("開始資料完整性驗證")
    logger.info("=" * 80)
    
    overall_result = ValidationResult()
    
    try:
        # 連線 ClickHouse
        client = connect_clickhouse()
        
        # 驗證同步新鮮度
        freshness_result = validate_sync_freshness(client)
        for r in freshness_result.results:
            overall_result.add_result(r["table"], r["test"], r["status"], 
                                    r["mssql_count"], r["clickhouse_count"], r["message"])
        
        # 驗證各表筆數一致性
        for table_config in VALIDATION_TABLES:
            table_result = validate_table_counts(client, table_config)
            for r in table_result.results:
                overall_result.add_result(r["table"], r["test"], r["status"],
                                        r["mssql_count"], r["clickhouse_count"], r["message"])
        
        # 輸出結果
        overall_result.print_summary()
        overall_result.save_to_file()
        
        # 回傳結果
        if overall_result.failed_tests > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"驗證過程發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()