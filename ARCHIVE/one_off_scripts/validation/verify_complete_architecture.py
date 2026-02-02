#!/usr/bin/env python3
"""
完整架構驗證腳本
驗證 Bronze → Silver → Gold 層的表結構和資料狀態
以及 Cube.js 模型配置
"""

import clickhouse_connect
import sys
import os
from datetime import datetime

def main():
    try:
        # 連接 ClickHouse
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default'
        )
        
        print("🏗️ 完整架構驗證報告")
        print("=" * 60)
        print(f"驗證時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # ========================================
        # 1. Bronze 層驗證
        # ========================================
        print("📊 Bronze 層 (原生 Flowable 表)")
        print("-" * 40)
        
        bronze_tables = [
            'bronze.bpm_act_hi_taskinst',
            'bronze.bpm_act_hi_procinst', 
            'bronze.bpm_act_hi_varinst',
            'bronze.bpm_act_hi_identitylink',
            'bronze.bpm_act_re_procdef',
            'bronze.common_hr_employee'
        ]
        
        bronze_status = {}
        for table in bronze_tables:
            try:
                result = client.query(f"SELECT COUNT(*) FROM {table}")
                count = result.result_rows[0][0]
                bronze_status[table] = count
                print(f"   ✅ {table}: {count:,} 筆記錄")
            except Exception as e:
                bronze_status[table] = f"ERROR: {e}"
                print(f"   ❌ {table}: 錯誤 - {e}")
        
        # ========================================
        # 2. Silver 層驗證
        # ========================================
        print("\n📊 Silver 層 (MVIEW 自動更新)")
        print("-" * 40)
        
        silver_tables = [
            # 第一層 MVIEW
            'silver.mv_varinst_pivoted',
            'silver.mv_emp_user_groups',
            'silver.mv_emp_node_codes',
            'silver.mv_emp_org_info',
            'silver.mv_task_status_summary_native',
            # 第二層 MVIEW
            'silver.mv_fact_task_vx_attribution',
            'silver.mv_l5_metrics_realtime',
            # 維度表
            'silver.mv_dim_config_user'
        ]
        
        silver_status = {}
        for table in silver_tables:
            try:
                result = client.query(f"SELECT COUNT(*) FROM {table} FINAL")
                count = result.result_rows[0][0]
                silver_status[table] = count
                print(f"   ✅ {table}: {count:,} 筆記錄")
            except Exception as e:
                silver_status[table] = f"ERROR: {e}"
                print(f"   ❌ {table}: 錯誤 - {e}")
        
        # ========================================
        # 3. Gold 層驗證
        # ========================================
        print("\n📊 Gold 層 (快照表)")
        print("-" * 40)
        
        gold_tables = [
            'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT',
            'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV',
            'gold.DAILY_USER_UTILIZATION_SNAPSHOT'
        ]
        
        gold_status = {}
        for table in gold_tables:
            try:
                result = client.query(f"SELECT COUNT(*) FROM {table} FINAL")
                count = result.result_rows[0][0]
                gold_status[table] = count
                print(f"   ✅ {table}: {count:,} 筆記錄")
            except Exception as e:
                gold_status[table] = f"ERROR: {e}"
                print(f"   ❌ {table}: 錯誤 - {e}")
        
        # ========================================
        # 4. 關鍵測試案例驗證
        # ========================================
        print("\n🔍 關鍵測試案例驗證")
        print("-" * 40)
        
        # WJ2/NBU/E5 2025-12-25 測試案例
        test_sql = """
        SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE (
            toDate(task_create_time) = '2025-12-25'
            OR toDate(task_claim_time) = '2025-12-25'
            OR toDate(task_end_time) = '2025-12-25'
        )
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        """
        
        result = client.query(test_sql)
        test_count = result.result_rows[0][0]
        print(f"   WJ2/NBU/E5 2025-12-25: {test_count} 筆記錄")
        print(f"   MSSQL 參考: 5 筆記錄")
        
        if test_count == 5:
            print("   ✅ 測試通過！與 MSSQL 完全一致")
        else:
            print(f"   ⚠️ 測試結果: 預期 5 筆，實際 {test_count} 筆")
        
        # ========================================
        # 5. Cube.js 模型檢查
        # ========================================
        print("\n🧊 Cube.js 模型檢查")
        print("-" * 40)
        
        cube_models = [
            'cube/model/cubes/cube_gold_l5_task_completion.js',
            'cube/model/cubes/cube_gold_user_utilization.js'
        ]
        
        for model_path in cube_models:
            if os.path.exists(model_path):
                with open(model_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 檢查是否使用 Gold 層表
                    if 'gold.' in content:
                        print(f"   ✅ {model_path}: 使用 Gold 層表")
                    else:
                        print(f"   ⚠️ {model_path}: 未使用 Gold 層表")
            else:
                print(f"   ❌ {model_path}: 檔案不存在")
        
        # 檢查 docker-compose.yml
        docker_compose_path = 'cube/docker-compose.yml'
        if os.path.exists(docker_compose_path):
            print(f"   ✅ {docker_compose_path}: 配置檔案存在")
        else:
            print(f"   ❌ {docker_compose_path}: 配置檔案不存在")
        
        # ========================================
        # 6. 資料一致性總結
        # ========================================
        print("\n📈 資料一致性總結")
        print("-" * 40)
        
        # 計算 Bronze → Silver 對應關係
        if 'bronze.bpm_act_hi_taskinst' in bronze_status and 'silver.mv_fact_task_vx_attribution' in silver_status:
            bronze_tasks = bronze_status['bronze.bpm_act_hi_taskinst']
            silver_tasks = silver_status['silver.mv_fact_task_vx_attribution']
            if isinstance(bronze_tasks, int) and isinstance(silver_tasks, int):
                print(f"   Bronze → Silver: {bronze_tasks:,} → {silver_tasks:,}")
                if bronze_tasks > 0:
                    ratio = silver_tasks / bronze_tasks
                    print(f"   轉換比例: {ratio:.2f} (1:{ratio:.2f})")
        
        # 計算 Silver → Gold 對應關係
        if 'silver.mv_l5_metrics_realtime' in silver_status and 'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV' in gold_status:
            silver_metrics = silver_status['silver.mv_l5_metrics_realtime']
            gold_snapshot = gold_status['gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV']
            if isinstance(silver_metrics, int) and isinstance(gold_snapshot, int):
                print(f"   Silver → Gold: {silver_metrics:,} → {gold_snapshot:,}")
        
        # ========================================
        # 7. 架構完整性評估
        # ========================================
        print("\n🎯 架構完整性評估")
        print("-" * 40)
        
        # 統計各層狀態
        bronze_ok = sum(1 for v in bronze_status.values() if isinstance(v, int) and v > 0)
        bronze_total = len(bronze_status)
        
        silver_ok = sum(1 for v in silver_status.values() if isinstance(v, int) and v > 0)
        silver_total = len(silver_status)
        
        gold_ok = sum(1 for v in gold_status.values() if isinstance(v, int) and v > 0)
        gold_total = len(gold_status)
        
        print(f"   Bronze 層: {bronze_ok}/{bronze_total} 表正常 ({bronze_ok/bronze_total*100:.1f}%)")
        print(f"   Silver 層: {silver_ok}/{silver_total} 表正常 ({silver_ok/silver_total*100:.1f}%)")
        print(f"   Gold 層: {gold_ok}/{gold_total} 表正常 ({gold_ok/gold_total*100:.1f}%)")
        
        # 整體評估
        total_ok = bronze_ok + silver_ok + gold_ok
        total_tables = bronze_total + silver_total + gold_total
        overall_health = total_ok / total_tables * 100
        
        print(f"\n   整體架構健康度: {overall_health:.1f}% ({total_ok}/{total_tables} 表正常)")
        
        if overall_health >= 90:
            print("   🎉 架構狀態: 優秀")
        elif overall_health >= 80:
            print("   ✅ 架構狀態: 良好")
        elif overall_health >= 70:
            print("   ⚠️ 架構狀態: 需要注意")
        else:
            print("   ❌ 架構狀態: 需要修復")
        
        # 測試案例評估
        if test_count == 5:
            print("   ✅ 資料一致性: 與 MSSQL 完全一致")
        else:
            print("   ⚠️ 資料一致性: 需要進一步檢查")
        
        return overall_health >= 80 and test_count == 5
        
    except Exception as e:
        print(f"❌ 驗證失敗: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)