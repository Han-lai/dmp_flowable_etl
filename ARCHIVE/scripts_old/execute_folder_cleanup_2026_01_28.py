#!/usr/bin/env python3
"""
專案資料夾整理腳本 - 2026年1月28日
移動過期和測試檔案至 ARCHIVE，保留核心功能檔案
"""

import os
import shutil
from pathlib import Path

def create_archive_structure():
    """建立 ARCHIVE 子資料夾結構"""
    archive_dirs = [
        "ARCHIVE/scripts_old",
        "ARCHIVE/sql_old", 
        "ARCHIVE/logs_old",
        "ARCHIVE/misc"
    ]
    
    for dir_path in archive_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✅ 建立目錄: {dir_path}")

def move_scripts():
    """移動 scripts/ 中的過期檔案"""
    
    # 保留的核心腳本 (15個)
    keep_scripts = {
        "test_clickhouse_connection.py",
        "check_existing_tables.py", 
        "verify_mssql_clickhouse_reconciliation.py",
        "verify_mview_pipeline_completion.py",
        "debug_superset_cne_wj2_nbu_e5_2025_12_25.py",
        "execute_silver_dimension_update.py",
        "execute_gold_dimension_update.py",
        "backup_and_update_silver_mview.py",
        "explain_mdm_mapping_logic.py",
        "execute_mapping_compliance_validation.py",
        "execute_varinst_mdm_validation.py",
        "validate_silver_gold_mapping_compliance.py",
        "execute_end_to_end_pipeline.py",
        "verify_complete_architecture.py",
        "production_environment_test.py"
    }
    
    scripts_dir = Path("scripts")
    if not scripts_dir.exists():
        print("❌ scripts/ 目錄不存在")
        return
    
    moved_count = 0
    kept_count = 0
    
    for file_path in scripts_dir.iterdir():
        if file_path.is_file() and file_path.suffix == '.py':
            if file_path.name in keep_scripts:
                print(f"✅ 保留: scripts/{file_path.name}")
                kept_count += 1
            else:
                # 移動到 ARCHIVE
                dest_path = Path("ARCHIVE/scripts_old") / file_path.name
                shutil.move(str(file_path), str(dest_path))
                print(f"📦 移動: scripts/{file_path.name} → ARCHIVE/scripts_old/")
                moved_count += 1
        elif file_path.is_file() and file_path.suffix in ['.md', '.txt']:
            # 移動報告檔案
            dest_path = Path("ARCHIVE/scripts_old") / file_path.name
            shutil.move(str(file_path), str(dest_path))
            print(f"📦 移動: scripts/{file_path.name} → ARCHIVE/scripts_old/")
            moved_count += 1
    
    print(f"\n📊 scripts/ 整理完成: 保留 {kept_count} 個，移動 {moved_count} 個")

def move_sql_files():
    """移動 sql/ 中的過期檔案"""
    
    # 保留的核心 SQL (8個)
    keep_sql = {
        "create_silver_dim_mfg_five_level.sql",
        "update_silver_dimension_backfill_logic.sql", 
        "update_gold_dimension_backfill_logic.sql",
        "validate_dimension_backfill_logic.sql",
        "validate_varinst_mdm_mapping.sql",
        "validate_silver_gold_mapping_compliance.sql",
        "corrected_varinst_mdm_mapping_demo.sql",
        "END_TO_END_EXECUTION_GUIDE.md"
    }
    
    sql_dir = Path("sql")
    if not sql_dir.exists():
        print("❌ sql/ 目錄不存在")
        return
    
    moved_count = 0
    kept_count = 0
    
    for file_path in sql_dir.iterdir():
        if file_path.is_file():
            if file_path.name in keep_sql:
                print(f"✅ 保留: sql/{file_path.name}")
                kept_count += 1
            else:
                # 移動到 ARCHIVE
                dest_path = Path("ARCHIVE/sql_old") / file_path.name
                shutil.move(str(file_path), str(dest_path))
                print(f"📦 移動: sql/{file_path.name} → ARCHIVE/sql_old/")
                moved_count += 1
    
    print(f"\n📊 sql/ 整理完成: 保留 {kept_count} 個，移動 {moved_count} 個")

def move_logs():
    """移動 logs/ 中的舊檔案"""
    
    # 保留重要日誌
    keep_logs = {
        "data_inconsistency_analysis_20260123_143000.md"
    }
    
    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("❌ logs/ 目錄不存在")
        return
    
    moved_count = 0
    kept_count = 0
    latest_sync_file = None
    latest_sync_time = 0
    
    # 找到最新的 sync_incremental 檔案
    for file_path in logs_dir.iterdir():
        if file_path.is_file() and file_path.name.startswith("sync_incremental_"):
            if file_path.stat().st_mtime > latest_sync_time:
                latest_sync_time = file_path.stat().st_mtime
                latest_sync_file = file_path.name
    
    if latest_sync_file:
        keep_logs.add(latest_sync_file)
    
    for file_path in logs_dir.iterdir():
        if file_path.is_file():
            if file_path.name in keep_logs:
                print(f"✅ 保留: logs/{file_path.name}")
                kept_count += 1
            else:
                # 移動到 ARCHIVE
                dest_path = Path("ARCHIVE/logs_old") / file_path.name
                shutil.move(str(file_path), str(dest_path))
                print(f"📦 移動: logs/{file_path.name} → ARCHIVE/logs_old/")
                moved_count += 1
    
    print(f"\n📊 logs/ 整理完成: 保留 {kept_count} 個，移動 {moved_count} 個")

def move_root_files():
    """移動根目錄的過期檔案"""
    
    # 移動的根目錄檔案
    move_files = {
        "REFACTOR_REPORT.md",
        "REORGANIZATION_SUMMARY.md", 
        "MSSQL_CLICKHOUSE_RECONCILIATION_SUCCESS.md",
        "TODO_DATA_VALIDATION.md"
    }
    
    moved_count = 0
    
    for filename in move_files:
        file_path = Path(filename)
        if file_path.exists():
            dest_path = Path("ARCHIVE/misc") / filename
            shutil.move(str(file_path), str(dest_path))
            print(f"📦 移動: {filename} → ARCHIVE/misc/")
            moved_count += 1
        else:
            print(f"⚠️ 檔案不存在: {filename}")
    
    print(f"\n📊 根目錄整理完成: 移動 {moved_count} 個檔案")

def main():
    """主執行函數"""
    print("🚀 開始執行專案資料夾整理")
    print("=" * 60)
    
    # 1. 建立 ARCHIVE 結構
    print("\n1️⃣ 建立 ARCHIVE 資料夾結構")
    create_archive_structure()
    
    # 2. 移動 scripts
    print("\n2️⃣ 整理 scripts/ 資料夾")
    move_scripts()
    
    # 3. 移動 sql
    print("\n3️⃣ 整理 sql/ 資料夾") 
    move_sql_files()
    
    # 4. 移動 logs
    print("\n4️⃣ 整理 logs/ 資料夾")
    move_logs()
    
    # 5. 移動根目錄檔案
    print("\n5️⃣ 整理根目錄檔案")
    move_root_files()
    
    print("\n" + "=" * 60)
    print("🎉 專案資料夾整理完成！")
    print("📁 所有過期檔案已移至 ARCHIVE/ 對應子資料夾")
    print("✅ 核心功能檔案已保留在原位置")
    print("🔄 如需復原，可從 ARCHIVE/ 移回原位置")

if __name__ == "__main__":
    main()