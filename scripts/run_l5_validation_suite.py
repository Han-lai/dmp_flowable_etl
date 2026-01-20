#!/usr/bin/env python3
"""
========================================
L5 指標完整驗證套件
========================================
執行所有 L5 任務執行完成率指標的驗證腳本：
1. 基礎資料一致性驗證
2. L5 業務規則驗證
3. 邊界案例驗證
4. Gold 層聚合驗證（如果可用）

提供完整的 L5 指標驗證報告
"""

import subprocess
import sys
import logging
from datetime import datetime
import os

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_script(script_name, description, args=None):
    """執行驗證腳本"""
    logger.info(f"\n{'='*80}")
    logger.info(f"執行: {description}")
    logger.info(f"腳本: {script_name}")
    logger.info('='*80)
    
    try:
        cmd = [sys.executable, script_name]
        if args:
            cmd.extend(args)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # 輸出腳本結果
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        success = result.returncode == 0
        
        if success:
            logger.info(f"✅ {description} - 執行成功")
        else:
            logger.error(f"❌ {description} - 執行失敗 (返回碼: {result.returncode})")
        
        return success, result.stdout, result.stderr
        
    except Exception as e:
        logger.error(f"❌ {description} - 執行異常: {e}")
        return False, "", str(e)


def extract_test_results(stdout):
    """從腳本輸出中提取測試結果"""
    results = {}
    lines = stdout.split('\n')
    
    for line in lines:
        line = line.strip()
        if '✅' in line and '通過' in line:
            # 提取測試項目名稱
            if ':' in line:
                test_name = line.split(':')[0].replace('✅', '').strip()
                results[test_name] = 'PASS'
        elif '❌' in line and ('失敗' in line or '不一致' in line):
            if ':' in line:
                test_name = line.split(':')[0].replace('❌', '').strip()
                results[test_name] = 'FAIL'
    
    return results


def main():
    """主程式"""
    logger.info("=" * 100)
    logger.info("L5 任務執行完成率指標 - 完整驗證套件")
    logger.info("=" * 100)
    logger.info("執行所有相關驗證腳本，提供完整的驗證報告")
    logger.info("=" * 100)
    
    start_time = datetime.now()
    
    # 定義要執行的驗證腳本
    validation_scripts = [
        {
            'script': 'verify_reference_sql.py',
            'description': '參考案例驗證 (12 筆基準資料)',
            'category': '基礎驗證'
        },
        {
            'script': 'verify_random_conditions.py',
            'description': '隨機條件驗證 (5 組隨機測試)',
            'category': '基礎驗證'
        },
        {
            'script': 'verify_clickhouse_vs_mssql.py',
            'description': 'ClickHouse vs MSSQL 對帳驗證',
            'category': '基礎驗證'
        },
        {
            'script': 'verify_l5_business_rules.py',
            'description': 'L5 業務規則驗證 (Vx 歸屬、工單號、排除邏輯)',
            'category': 'L5 業務規則'
        },
        {
            'script': 'verify_l5_edge_cases.py',
            'description': 'L5 邊界案例驗證 (NULL 值、特殊字符、混合條件)',
            'category': 'L5 邊界案例'
        }
    ]
    
    # 執行所有驗證腳本
    all_results = {}
    script_success = {}
    
    for script_info in validation_scripts:
        script_name = script_info['script']
        description = script_info['description']
        category = script_info['category']
        
        # 檢查腳本是否存在
        if not os.path.exists(script_name):
            logger.warning(f"⚠️ 腳本不存在: {script_name}")
            script_success[script_name] = False
            continue
        
        # 執行腳本
        success, stdout, stderr = run_script(script_name, description)
        script_success[script_name] = success
        
        # 提取測試結果
        if success and stdout:
            test_results = extract_test_results(stdout)
            all_results[category] = all_results.get(category, {})
            all_results[category].update(test_results)
    
    # 生成總結報告
    elapsed = (datetime.now() - start_time).total_seconds()
    
    logger.info("\n" + "=" * 100)
    logger.info("L5 指標驗證套件 - 總結報告")
    logger.info("=" * 100)
    
    # 腳本執行狀況
    logger.info("\n📋 腳本執行狀況:")
    logger.info("-" * 60)
    total_scripts = len(validation_scripts)
    successful_scripts = sum(1 for success in script_success.values() if success)
    
    for script_info in validation_scripts:
        script_name = script_info['script']
        description = script_info['description']
        
        if script_name in script_success:
            status = "✅ 成功" if script_success[script_name] else "❌ 失敗"
        else:
            status = "⚠️ 未找到"
        
        logger.info(f"  {script_name:<30} {status}")
    
    logger.info(f"\n腳本執行成功率: {successful_scripts}/{total_scripts} ({successful_scripts/total_scripts*100:.1f}%)")
    
    # 測試結果詳情
    if all_results:
        logger.info("\n🧪 測試結果詳情:")
        logger.info("-" * 60)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in all_results.items():
            logger.info(f"\n📂 {category}:")
            for test_name, result in tests.items():
                status_icon = "✅" if result == 'PASS' else "❌"
                logger.info(f"  {status_icon} {test_name}")
                total_tests += 1
                if result == 'PASS':
                    passed_tests += 1
        
        if total_tests > 0:
            logger.info(f"\n測試通過率: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
    
    # 整體評估
    logger.info("\n🎯 整體評估:")
    logger.info("-" * 60)
    
    if successful_scripts == total_scripts:
        if all_results and passed_tests == total_tests:
            logger.info("🎉 完美！所有驗證腳本執行成功，所有測試通過")
            logger.info("L5 任務執行完成率指標實作與 MSSQL 原始邏輯完全一致")
            overall_status = "EXCELLENT"
        else:
            logger.info("✅ 良好！所有驗證腳本執行成功，但部分測試未通過")
            logger.info("建議檢查失敗的測試項目")
            overall_status = "GOOD"
    else:
        logger.error("⚠️ 需要改善！部分驗證腳本執行失敗")
        logger.error("請檢查腳本執行環境和依賴")
        overall_status = "NEEDS_IMPROVEMENT"
    
    # 建議行動
    logger.info("\n📝 建議行動:")
    logger.info("-" * 60)
    
    if overall_status == "EXCELLENT":
        logger.info("✅ L5 指標已準備好進入生產環境")
        logger.info("✅ 可以開始建立 Gold 層聚合驗證")
        logger.info("✅ 可以開始端到端效能測試")
    elif overall_status == "GOOD":
        logger.info("⚠️ 修復失敗的測試項目")
        logger.info("⚠️ 重新執行驗證確保一致性")
        logger.info("✅ 基礎架構穩定，可繼續開發")
    else:
        logger.info("❌ 修復腳本執行問題")
        logger.info("❌ 檢查資料庫連線和權限")
        logger.info("❌ 確保所有依賴腳本存在")
    
    # 下一步建議
    logger.info("\n🚀 下一步建議:")
    logger.info("-" * 60)
    logger.info("1. 建立 Gold 層聚合邏輯驗證腳本")
    logger.info("2. 實作累計在途任務數 (Todo + Doing Acc) 邏輯")
    logger.info("3. 加入 'total' 時間區間類型")
    logger.info("4. 建立端到端效能測試")
    logger.info("5. 建立自動化驗證流程")
    
    logger.info(f"\n⏱️ 總執行時間: {elapsed:.2f} 秒")
    logger.info("=" * 100)
    
    # 返回適當的退出碼
    if overall_status == "EXCELLENT":
        sys.exit(0)
    elif overall_status == "GOOD":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()