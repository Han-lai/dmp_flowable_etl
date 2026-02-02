#!/usr/bin/env python3
"""
安裝驗證腳本
檢查所有必要元件是否正確安裝和設定
"""

import os
import sys
import time
import logging
import subprocess
import requests
from pathlib import Path
import clickhouse_connect

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# 設定
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

JDBC_BRIDGE_URL = "http://localhost:9019"
CUBEJS_URL = "http://localhost:4000"

class VerificationResult:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
    
    def add_test(self, name, status, message=""):
        self.tests.append({
            "name": name,
            "status": status,
            "message": message
        })
        if status == "PASS":
            self.passed += 1
        else:
            self.failed += 1
    
    def print_summary(self):
        print("\n" + "=" * 80)
        print("驗證結果摘要")
        print("=" * 80)
        
        for test in self.tests:
            status_icon = "✅" if test["status"] == "PASS" else "❌"
            print(f"{status_icon} {test['name']:<50} {test['status']}")
            if test["message"]:
                print(f"   {test['message']}")
        
        print("-" * 80)
        print(f"總計: {len(self.tests)} 項測試")
        print(f"通過: {self.passed} 項")
        print(f"失敗: {self.failed} 項")
        print("=" * 80)
        
        if self.failed == 0:
            print("🎉 所有驗證項目都通過了！系統已準備就緒。")
        else:
            print("⚠️ 有部分驗證項目失敗，請檢查相關設定。")

def test_python_packages():
    """測試 Python 套件"""
    result = VerificationResult()
    
    required_packages = [
        "clickhouse_connect",
        "pandas", 
        "requests"
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            result.add_test(f"Python 套件: {package}", "PASS")
        except ImportError:
            result.add_test(f"Python 套件: {package}", "FAIL", f"請執行: pip install {package}")
    
    return result

def test_clickhouse_connection():
    """測試 ClickHouse 連線"""
    result = VerificationResult()
    
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        response = client.command("SELECT 1")
        result.add_test("ClickHouse 連線", "PASS", f"連線成功: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
        
        # 測試資料庫
        databases = client.command("SHOW DATABASES")
        if "bronze" in str(databases):
            result.add_test("Bronze 資料庫", "PASS")
        else:
            result.add_test("Bronze 資料庫", "FAIL", "bronze 資料庫不存在，請執行 initialize_database.py")
            
    except Exception as e:
        result.add_test("ClickHouse 連線", "FAIL", str(e))
    
    return result

def test_jdbc_bridge():
    """測試 JDBC Bridge"""
    result = VerificationResult()
    
    try:
        # 檢查 JDBC Bridge 服務
        response = requests.get(f"{JDBC_BRIDGE_URL}/ping", timeout=5)
        if response.status_code == 200:
            result.add_test("JDBC Bridge 服務", "PASS")
        else:
            result.add_test("JDBC Bridge 服務", "FAIL", f"HTTP {response.status_code}")
            
        # 測試 JDBC 查詢
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        jdbc_test = client.query("SELECT * FROM jdbc('mssql_master', 'SELECT 1 as test')")
        if jdbc_test.result_rows:
            result.add_test("JDBC Bridge 查詢", "PASS")
        else:
            result.add_test("JDBC Bridge 查詢", "FAIL", "無法透過 JDBC Bridge 查詢 MSSQL")
            
    except requests.exceptions.RequestException:
        result.add_test("JDBC Bridge 服務", "FAIL", "服務無回應，請檢查 Docker 容器狀態")
    except Exception as e:
        result.add_test("JDBC Bridge 查詢", "FAIL", str(e))
    
    return result

def test_docker_services():
    """測試 Docker 服務"""
    result = VerificationResult()
    
    try:
        # 檢查 Docker 是否運行
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        result.add_test("Docker 安裝", "PASS")
        
        # 檢查 Docker Compose
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
        result.add_test("Docker Compose 安裝", "PASS")
        
        # 檢查容器狀態
        containers_output = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"],
            capture_output=True, text=True
        )
        
        if "clickhouse-server" in containers_output.stdout:
            result.add_test("ClickHouse 容器", "PASS")
        else:
            result.add_test("ClickHouse 容器", "FAIL", "容器未運行，請執行 docker-compose up -d")
            
        if "clickhouse-jdbc-bridge" in containers_output.stdout:
            result.add_test("JDBC Bridge 容器", "PASS")
        else:
            result.add_test("JDBC Bridge 容器", "FAIL", "容器未運行，請檢查 docker-compose.yml")
            
    except subprocess.CalledProcessError:
        result.add_test("Docker 安裝", "FAIL", "Docker 未安裝或未啟動")
    except FileNotFoundError:
        result.add_test("Docker 安裝", "FAIL", "找不到 Docker 指令")
    
    return result

def test_cube_js():
    """測試 Cube.js"""
    result = VerificationResult()
    
    try:
        response = requests.get(f"{CUBEJS_URL}/cubejs-api/v1/meta", timeout=10)
        if response.status_code == 200:
            result.add_test("Cube.js 服務", "PASS")
            
            # 檢查資料模型
            meta_data = response.json()
            if "cubes" in meta_data:
                cube_count = len(meta_data["cubes"])
                result.add_test("Cube.js 資料模型", "PASS", f"載入 {cube_count} 個 Cube")
            else:
                result.add_test("Cube.js 資料模型", "FAIL", "未找到資料模型")
        else:
            result.add_test("Cube.js 服務", "FAIL", f"HTTP {response.status_code}")
            
    except requests.exceptions.RequestException:
        result.add_test("Cube.js 服務", "FAIL", "服務無回應，請檢查 Cube.js 容器狀態")
    
    return result

def test_file_structure():
    """測試檔案結構"""
    result = VerificationResult()
    
    project_root = Path(__file__).parent.parent.parent
    
    required_files = [
        "README.md",
        "GETTING_STARTED.md", 
        "ARCHITECTURE.md",
        "clickhouse/ddl/10_bronze_sources.sql",
        "cube/model/cubes/cube_gold_l5_task_completion.js",
        "docker/docker-compose.yml"
    ]
    
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            result.add_test(f"檔案: {file_path}", "PASS")
        else:
            result.add_test(f"檔案: {file_path}", "FAIL", "檔案不存在")
    
    return result

def main():
    """主程式"""
    logger.info("=" * 80)
    logger.info("開始系統安裝驗證")
    logger.info("=" * 80)
    
    all_results = VerificationResult()
    
    # 執行各項測試
    tests = [
        ("Python 套件", test_python_packages),
        ("檔案結構", test_file_structure),
        ("Docker 服務", test_docker_services),
        ("ClickHouse", test_clickhouse_connection),
        ("JDBC Bridge", test_jdbc_bridge),
        ("Cube.js", test_cube_js)
    ]
    
    for test_name, test_func in tests:
        logger.info(f"執行 {test_name} 測試...")
        result = test_func()
        
        # 合併結果
        for test in result.tests:
            all_results.add_test(test["name"], test["status"], test["message"])
    
    # 輸出結果
    all_results.print_summary()
    
    # 回傳結果
    if all_results.failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()