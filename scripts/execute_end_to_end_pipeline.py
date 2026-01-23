#!/usr/bin/env python3
"""
ClickHouse 金銀銅資料層 End-to-End 執行腳本
完整建置 Bronze → Silver → Gold 資料倉儲
"""

import sys
import time
from pathlib import Path
from typing import List, Tuple

def get_execution_order() -> List[Tuple[str, str, str]]:
    """
    返回完整的執行順序
    格式：(階段, 檔案路徑, 描述)
    """
    return [
        # 階段 1：Bronze 層（銅層）
        ("Bronze", "sql/01_create_database.sql", "建立資料庫結構"),
        ("Bronze", "sql/02_create_bpm_tables.sql", "建立 BPM 相關表（Flowable 資料）"),
        ("Bronze", "sql/03_create_common_tables.sql", "建立共用表（HR、MDM 等）"),
        
        # 階段 2：Silver 層（銀層）
        ("Silver", "sql/04_create_silver_database.sql", "建立 Silver 資料庫"),
        ("Silver", "sql/11_create_silver_mviews_layer1.sql", "建立 Silver 第一層 MVIEW（基礎轉換）"),
        ("Silver", "sql/12_create_silver_mviews_layer2_fixed.sql", "建立 Silver 第二層 MVIEW（修正版本）⭐"),
        ("Silver", "sql/create_silver_dim_mfg_five_level.sql", "建立製造五階維度"),
        
        # 階段 3：Gold 層（金層）
        ("Gold", "sql/13_create_gold_mviews.sql", "建立 Gold 層 MVIEW（最終指標）"),
        
        # 階段 4：驗證
        ("Validation", "sql/test_mssql_date_filter_logic.sql", "執行驗證查詢"),
    ]

def check_files_exist(execution_order: List[Tuple[str, str, str]]) -> Tuple[bool, List[str]]:
    """檢查所有必要檔案是否存在"""
    missing_files = []
    
    for stage, file_path, description in execution_order:
        if not Path(file_path).exists():
            missing_files.append(f"{file_path} ({description})")
    
    return len(missing_files) == 0, missing_files

def print_execution_plan(execution_order: List[Tuple[str, str, str]]):
    """顯示執行計劃"""
    print("📋 ClickHouse 金銀銅資料層執行計劃")
    print("=" * 60)
    
    current_stage = ""
    step_number = 1
    
    for stage, file_path, description in execution_order:
        if stage != current_stage:
            current_stage = stage
            print(f"\n🏗️ 階段：{stage} 層")
            print("-" * 40)
        
        status_icon = "⭐" if "fixed" in file_path else "📄"
        print(f"{step_number:2d}. {status_icon} {file_path}")
        print(f"    {description}")
        step_number += 1

def print_validation_queries():
    """顯示關鍵驗證查詢"""
    print("\n🔍 關鍵驗證查詢")
    print("=" * 40)
    
    queries = [
        ("Bronze 層驗證", """
SELECT 'Bronze 層 BPM 任務表' AS check_name, COUNT(*) AS record_count
FROM bronze.bpm_act_hi_taskinst;
        """),
        
        ("Silver 層驗證", """
SELECT 'Silver 層事實表' AS check_name, COUNT(*) AS record_count
FROM silver.mv_fact_task_vx_attribution FINAL;
        """),
        
        ("關鍵測試案例", """
-- WJ2/NBU/E5 2025-12-25 應為 5 筆（與 MSSQL 一致）
SELECT 'WJ2/NBU/E5 2025-12-25 測試' AS check_name, COUNT(*) AS record_count
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5';
-- 預期結果：5 筆
        """),
        
        ("Gold 層驗證", """
SELECT 'Gold 層聚合表' AS check_name, COUNT(*) AS record_count
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL;
        """)
    ]
    
    for name, query in queries:
        print(f"\n📊 {name}:")
        print(query.strip())

def main():
    print("🚀 ClickHouse 金銀銅資料層 End-to-End 執行指南")
    print("=" * 60)
    
    # 取得執行順序
    execution_order = get_execution_order()
    
    # 檢查檔案是否存在
    all_files_exist, missing_files = check_files_exist(execution_order)
    
    if not all_files_exist:
        print("❌ 缺少必要檔案:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n請確保所有檔案存在後再執行。")
        return False
    
    print("✅ 所有必要檔案已確認存在")
    
    # 顯示執行計劃
    print_execution_plan(execution_order)
    
    # 顯示重要注意事項
    print("\n⚠️ 重要注意事項")
    print("=" * 40)
    print("1. 🔧 使用修正版本：sql/12_create_silver_mviews_layer2_fixed.sql")
    print("2. 📊 關鍵驗證：WJ2/NBU/E5 2025-12-25 應為 5 筆記錄")
    print("3. 🔄 MVIEW 更新：使用 FINAL 關鍵字查詢最新資料")
    print("4. 🚨 已知問題：原版 Silver 層有日期過濾邏輯問題")
    
    # 顯示執行方式
    print("\n🛠️ 執行方式")
    print("=" * 40)
    print("方式 1 - 手動執行（推薦）:")
    print("  依序執行各 SQL 檔案")
    print("  clickhouse-client < sql/01_create_database.sql")
    print("  clickhouse-client < sql/02_create_bpm_tables.sql")
    print("  # ... 依序執行所有檔案")
    
    print("\n方式 2 - 批次執行:")
    print("  建立批次腳本整合所有 SQL")
    
    print("\n方式 3 - Python 腳本:")
    print("  使用 clickhouse-connect 逐一執行")
    
    # 顯示驗證查詢
    print_validation_queries()
    
    # 顯示故障排除
    print("\n🔧 故障排除")
    print("=" * 40)
    print("1. 資料膨脹問題 → 使用修正版本 SQL")
    print("2. 日期過濾不一致 → 執行 test_mssql_date_filter_logic.sql")
    print("3. MVIEW 更新延遲 → 檢查 _mview_update_time")
    print("4. JOIN 笛卡爾積 → 檢查 mv_varinst_pivoted 重複")
    
    print("\n✨ 執行完成後預期結果")
    print("=" * 40)
    print("- Bronze 層：原始資料同步完成")
    print("- Silver 層：業務邏輯轉換完成，日期過濾修正")
    print("- Gold 層：聚合指標計算完成")
    print("- 驗證：WJ2/NBU/E5 2025-12-25 = 5 筆（與 MSSQL 一致）")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)