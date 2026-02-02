#!/usr/bin/env python3
"""
Backfill 完成後的全管線刷新腳本
依序執行 Silver 和 Gold 層的維度補齊邏輯更新，確保 MView 反映最新的 Bronze 資料
"""

import subprocess
import sys
import time

def run_script(script_path, description):
    print(f"\n{'='*80}")
    print(f"🚀 開始執行: {description}")
    print(f"📂 腳本路徑: {script_path}")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    try:
        # 使用當前 Python 環境執行
        result = subprocess.run(
            [sys.executable, script_path],
            check=True,
            text=True
        )
        
        duration = time.time() - start_time
        print(f"\n✅ {description} 執行成功 (耗時: {duration:.2f} 秒)")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} 執行失敗 (Exit Code: {e.returncode})")
        return False
    except Exception as e:
        print(f"\n❌ {description} 發生未預期錯誤: {e}")
        return False

def main():
    print("🔄 開始全管線刷新程序 (Pipeline Refresh)")
    print("用途: 在 Bronze 層資料補齊 (Backfill) 完成後，強制更新 Silver/Gold 層資料")
    
    # 1. 更新 Silver 層
    # 這會重建 mv_fact_task_vx_attribution_mdm，重新計算 VarInst 和 MDM 維度
    if not run_script('scripts/execute_silver_dimension_update.py', 'Silver 層維度補齊更新'):
        print("⛔ Silver 層更新失敗，終止程序")
        sys.exit(1)
        
    # 休息一下，確保 ClickHouse 處理完畢
    print("\n⏳ 等待 5 秒確保系統穩定...")
    time.sleep(5)
    
    # 2. 更新 Gold 層
    # 這會重建 Daily Snapshot 和 Dashboard Summary
    if not run_script('scripts/execute_gold_dimension_update.py', 'Gold 層彙總更新'):
        print("⛔ Gold 層更新失敗，終止程序")
        sys.exit(1)
        
    print(f"\n{'='*80}")
    print("🎉 全管線刷新完成！")
    print("現在 Silver 和 Gold 層應該已經反映了最新的 Bronze 資料")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
