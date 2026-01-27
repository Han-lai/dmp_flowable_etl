#!/usr/bin/env python3
"""
一鍵部署腳本
自動執行完整的系統部署流程
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

class DeploymentStep:
    def __init__(self, name, description, command, required=True):
        self.name = name
        self.description = description
        self.command = command
        self.required = required
        self.status = "pending"
        self.duration = 0
        self.error = None

class Deployer:
    def __init__(self):
        self.steps = []
        self.project_root = Path(__file__).parent
        
    def add_step(self, step):
        self.steps.append(step)
    
    def run_command(self, command, cwd=None):
        """執行命令"""
        if cwd is None:
            cwd = self.project_root
            
        logger.info(f"執行命令: {command}")
        
        try:
            if isinstance(command, str):
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 分鐘超時
                )
            else:
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=600
                )
            
            if result.returncode == 0:
                logger.info("命令執行成功")
                if result.stdout:
                    logger.debug(f"輸出: {result.stdout}")
                return True, result.stdout
            else:
                logger.error(f"命令執行失敗 (退出碼: {result.returncode})")
                logger.error(f"錯誤輸出: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            logger.error("命令執行超時")
            return False, "命令執行超時"
        except Exception as e:
            logger.error(f"命令執行異常: {e}")
            return False, str(e)
    
    def execute_step(self, step):
        """執行單個部署步驟"""
        logger.info("=" * 60)
        logger.info(f"執行步驟: {step.name}")
        logger.info(f"說明: {step.description}")
        logger.info("=" * 60)
        
        start_time = time.perf_counter()
        
        try:
            if callable(step.command):
                # 如果是函數，直接呼叫
                success, output = step.command()
            else:
                # 如果是命令字串，執行命令
                success, output = self.run_command(step.command)
            
            step.duration = time.perf_counter() - start_time
            
            if success:
                step.status = "success"
                logger.info(f"✅ {step.name} 完成，耗時 {step.duration:.2f} 秒")
            else:
                step.status = "failed"
                step.error = output
                logger.error(f"❌ {step.name} 失敗，耗時 {step.duration:.2f} 秒")
                logger.error(f"錯誤: {output}")
                
        except Exception as e:
            step.duration = time.perf_counter() - start_time
            step.status = "failed"
            step.error = str(e)
            logger.error(f"❌ {step.name} 異常，耗時 {step.duration:.2f} 秒")
            logger.error(f"異常: {e}")
        
        return step.status == "success"
    
    def check_prerequisites(self):
        """檢查前置條件"""
        logger.info("檢查前置條件...")
        
        # 檢查 Docker
        success, _ = self.run_command("docker --version")
        if not success:
            logger.error("Docker 未安裝或未啟動")
            return False
        
        # 檢查 Docker Compose
        success, _ = self.run_command("docker-compose --version")
        if not success:
            logger.error("Docker Compose 未安裝")
            return False
        
        # 檢查 Python
        success, _ = self.run_command("python --version")
        if not success:
            logger.error("Python 未安裝")
            return False
        
        logger.info("✅ 前置條件檢查通過")
        return True
    
    def deploy(self):
        """執行完整部署"""
        logger.info("🚀 開始一鍵部署 DMP Flowable 系統")
        logger.info("=" * 80)
        
        total_start = time.perf_counter()
        
        # 檢查前置條件
        if not self.check_prerequisites():
            logger.error("前置條件檢查失敗，停止部署")
            return False
        
        # 執行所有步驟
        success_count = 0
        failed_count = 0
        
        for step in self.steps:
            success = self.execute_step(step)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
                
                if step.required:
                    logger.error(f"必要步驟 {step.name} 失敗，停止部署")
                    break
                else:
                    logger.warning(f"可選步驟 {step.name} 失敗，繼續部署")
        
        # 輸出結果摘要
        total_duration = time.perf_counter() - total_start
        
        logger.info("=" * 80)
        logger.info("部署結果摘要")
        logger.info("=" * 80)
        
        for step in self.steps:
            status_icon = "✅" if step.status == "success" else "❌" if step.status == "failed" else "⏸️"
            logger.info(f"{status_icon} {step.name:<40} {step.duration:>8.2f}s")
        
        logger.info("-" * 80)
        logger.info(f"總耗時: {total_duration:.2f} 秒")
        logger.info(f"成功: {success_count} 項")
        logger.info(f"失敗: {failed_count} 項")
        logger.info("=" * 80)
        
        if failed_count == 0:
            logger.info("🎉 部署完成！系統已準備就緒。")
            logger.info("\n下一步:")
            logger.info("1. 檢查服務狀態: docker-compose ps")
            logger.info("2. 查看 Cube.js: http://localhost:4000")
            logger.info("3. 執行驗證: python scripts/setup/verify_installation.py")
            return True
        else:
            logger.error("⚠️ 部署過程中有錯誤，請檢查日誌")
            return False

def setup_docker_services():
    """設定 Docker 服務"""
    deployer = Deployer()
    
    # 進入 docker 目錄並啟動服務
    docker_dir = deployer.project_root / "docker"
    
    # 檢查 docker-compose.yml 是否存在
    compose_file = docker_dir / "docker-compose.yml"
    if not compose_file.exists():
        return False, f"找不到 {compose_file}"
    
    # 啟動服務
    success, output = deployer.run_command("docker-compose up -d", cwd=docker_dir)
    
    if success:
        # 等待服務啟動
        time.sleep(10)
        
        # 檢查服務狀態
        success2, status_output = deployer.run_command("docker-compose ps", cwd=docker_dir)
        if success2:
            logger.info("Docker 服務狀態:")
            logger.info(status_output)
    
    return success, output

def setup_cube_js():
    """設定 Cube.js"""
    deployer = Deployer()
    
    cube_dir = deployer.project_root / "cube"
    
    # 檢查 cube 目錄
    if not cube_dir.exists():
        return False, "cube 目錄不存在"
    
    # 啟動 Cube.js
    success, output = deployer.run_command("docker-compose up -d", cwd=cube_dir)
    
    if success:
        # 等待服務啟動
        time.sleep(15)
        
        # 測試 Cube.js API
        try:
            import requests
            response = requests.get("http://localhost:4000/cubejs-api/v1/meta", timeout=10)
            if response.status_code == 200:
                logger.info("Cube.js API 回應正常")
            else:
                logger.warning(f"Cube.js API 回應異常: {response.status_code}")
        except Exception as e:
            logger.warning(f"無法測試 Cube.js API: {e}")
    
    return success, output

def main():
    """主程式"""
    deployer = Deployer()
    
    # 定義部署步驟
    steps = [
        DeploymentStep(
            "Docker 服務啟動",
            "啟動 ClickHouse 和 JDBC Bridge",
            setup_docker_services,
            required=True
        ),
        DeploymentStep(
            "資料庫初始化",
            "執行 DDL 腳本建立資料庫結構",
            "python scripts/setup/initialize_database.py",
            required=True
        ),
        DeploymentStep(
            "初始資料同步",
            "同步 MSSQL 資料到 ClickHouse",
            "python scripts/sync/sync_initial_data.py",
            required=True
        ),
        DeploymentStep(
            "Cube.js 啟動",
            "啟動 Cube.js 語意層服務",
            setup_cube_js,
            required=False
        ),
        DeploymentStep(
            "資料完整性驗證",
            "驗證資料同步正確性",
            "python scripts/validation/verify_data_integrity.py",
            required=False
        ),
        DeploymentStep(
            "安裝驗證",
            "驗證所有元件正常運作",
            "python scripts/setup/verify_installation.py",
            required=False
        )
    ]
    
    # 加入所有步驟
    for step in steps:
        deployer.add_step(step)
    
    # 執行部署
    success = deployer.deploy()
    
    # 回傳結果
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()