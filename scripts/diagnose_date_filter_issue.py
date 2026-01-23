#!/usr/bin/env python3
"""
日期過濾問題診斷腳本
診斷為何 Silver 層的日期過濾與 MSSQL 不一致
"""

import clickhouse_connect
import pandas as pd

class DateFilterDiagnostic:
    def __init__(self):
        self.ch_client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
    
    def check_mssql_date_logic(self):
        """分析 MSSQL 的日期過濾邏輯"""
        print("🔍 MSSQL 日期過濾邏輯分析")
        print("="*60)
        
        print("MSSQL 使用的日期過濾條件:")
        print("""
        WHERE (
               hti.START_TIME_ BETWEEN @startDateTime AND @endDateTime
            OR hti.CLAIM_TIME_ BETWEEN @startDateTime AND @endDateTime  
            OR hti.END_TIME_   BETWEEN @startDateTime AND @endDateTime
        )
        AND var_plant.TEXT_ = 'WJ2'
        AND var_factory.TEXT_ = 'NBU'
        AND var_lineName.TEXT_ = 'E5'
        
        其中：
        @startDateTime = '2025-12-25 00:00:00'
        @endDateTime   = '2025-12-25 23:59:59'
        """)
    
    def check_clickhouse_silver_date_logic(self):
        """檢查 ClickHouse Silver 層的日期過濾邏輯"""
        print("\n🔍 ClickHouse Silver 層日期過濾邏輯分析")
        print("="*60)
        
        print("Silver MVIEW 使用的日期過濾條件:")
        print("""
        WHERE toDate(task_create_time) = '2025-12-25'
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        
        問題：只檢查 task_create_time (START_TIME_)
        沒有檢查 task_claim_time (CLAIM_TIME_) 和 task_end_time (END_TIME_)
        """)
    
    def compare_date_filtering_results(self):
        """比較不同日期過濾方式的結果"""
        print("\n🔍 比較不同日期過濾方式的結果")
        print("="*60)
        
        # 方式 1: 只檢查 START_TIME_ (Silver 層目前的方式)
        method1_sql = """
        SELECT 
            'Method 1: Only START_TIME_' as method,
            COUNT(*) as record_count,
            COUNT(DISTINCT task_id) as unique_tasks
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE toDate(task_create_time) = '2025-12-25'
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        """
        
        # 方式 2: 檢查 START_TIME_, CLAIM_TIME_, END_TIME_ (MSSQL 的方式)
        method2_sql = """
        SELECT 
            'Method 2: START/CLAIM/END TIME' as method,
            COUNT(*) as record_count,
            COUNT(DISTINCT task_id) as unique_tasks
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE (
               toDate(task_create_time) = '2025-12-25'
            OR toDate(task_claim_time) = '2025-12-25'
            OR toDate(task_end_time) = '2025-12-25'
        )
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        """
        
        # 方式 3: 直接從 Bronze 層模擬 MSSQL 邏輯
        method3_sql = """
        SELECT 
            'Method 3: Bronze Layer MSSQL Logic' as method,
            COUNT(*) as record_count,
            COUNT(DISTINCT t.ID_) as unique_tasks
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        WHERE (
               t.START_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
            OR t.CLAIM_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
            OR t.END_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
        )
        AND v.varinst_plant = 'WJ2'
        AND v.varinst_factory = 'NBU'
        AND v.varinst_lineName = 'E5'
        """
        
        methods = [
            ("Method 1", method1_sql),
            ("Method 2", method2_sql),
            ("Method 3", method3_sql)
        ]
        
        results = []
        for method_name, sql in methods:
            try:
                df = self.ch_client.query_df(sql)
                record_count = df.iloc[0]['record_count']
                unique_tasks = df.iloc[0]['unique_tasks']
                results.append((method_name, record_count, unique_tasks))
                print(f"{method_name}: {record_count} 筆記錄, {unique_tasks} 個唯一任務")
            except Exception as e:
                print(f"{method_name}: 查詢失敗 - {e}")
                results.append((method_name, "ERROR", "ERROR"))
        
        return results
    
    def analyze_task_time_distribution(self):
        """分析任務時間分佈"""
        print("\n🔍 分析任務時間分佈")
        print("="*60)
        
        # 檢查 2025-12-25 的任務時間分佈
        time_dist_sql = """
        SELECT 
            toDate(task_create_time) as create_date,
            toDate(task_claim_time) as claim_date,
            toDate(task_end_time) as end_date,
            COUNT(*) as record_count
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE (
               toDate(task_create_time) = '2025-12-25'
            OR toDate(task_claim_time) = '2025-12-25'
            OR toDate(task_end_time) = '2025-12-25'
        )
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        GROUP BY create_date, claim_date, end_date
        ORDER BY record_count DESC
        LIMIT 10
        """
        
        time_df = self.ch_client.query_df(time_dist_sql)
        print("任務時間分佈 (前 10 種組合):")
        print(time_df.to_string(index=False))
        
        return time_df
    
    def check_specific_task_times(self):
        """檢查特定任務的時間"""
        print("\n🔍 檢查 MSSQL Reference 任務的時間")
        print("="*60)
        
        test_task_ids = [
            '117c3488-e0aa-11f0-8766-badd3bc212ac',
            'a84b6195-e124-11f0-8766-badd3bc212ac', 
            'a8cf860b-e124-11f0-8766-badd3bc212ac',
            'a96360f1-e124-11f0-8766-badd3bc212ac',
            'dc9fb8e2-e155-11f0-8766-badd3bc212ac'
        ]
        
        specific_sql = f"""
        SELECT 
            task_id,
            toString(task_create_time) as create_time,
            toString(task_claim_time) as claim_time,
            toString(task_end_time) as end_time,
            toDate(task_create_time) as create_date,
            toDate(task_claim_time) as claim_date,
            toDate(task_end_time) as end_date
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE task_id IN {tuple(test_task_ids)}
        ORDER BY task_create_time
        """
        
        specific_df = self.ch_client.query_df(specific_sql)
        print("MSSQL Reference 任務的時間資訊:")
        print(specific_df.to_string(index=False))
        
        return specific_df
    
    def find_extra_tasks(self):
        """找出額外的 183 筆任務"""
        print("\n🔍 找出額外的 183 筆任務 (188 - 5 = 183)")
        print("="*60)
        
        test_task_ids = [
            '117c3488-e0aa-11f0-8766-badd3bc212ac',
            'a84b6195-e124-11f0-8766-badd3bc212ac', 
            'a8cf860b-e124-11f0-8766-badd3bc212ac',
            'a96360f1-e124-11f0-8766-badd3bc212ac',
            'dc9fb8e2-e155-11f0-8766-badd3bc212ac'
        ]
        
        extra_sql = f"""
        SELECT 
            task_id,
            toString(task_create_time) as create_time,
            toString(task_claim_time) as claim_time,
            toString(task_end_time) as end_time,
            task_status,
            vx_type,
            mo_number
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE toDate(task_create_time) = '2025-12-25'
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        AND task_id NOT IN {tuple(test_task_ids)}
        ORDER BY task_create_time
        LIMIT 10
        """
        
        extra_df = self.ch_client.query_df(extra_sql)
        print("額外任務樣本 (前 10 筆):")
        print(extra_df.to_string(index=False))
        
        # 統計額外任務的特徵
        stats_sql = f"""
        SELECT 
            task_status,
            vx_type,
            COUNT(*) as count
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE toDate(task_create_time) = '2025-12-25'
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        AND task_id NOT IN {tuple(test_task_ids)}
        GROUP BY task_status, vx_type
        ORDER BY count DESC
        """
        
        stats_df = self.ch_client.query_df(stats_sql)
        print("\n額外任務統計:")
        print(stats_df.to_string(index=False))
        
        return extra_df, stats_df
    
    def generate_diagnostic_report(self):
        """產生診斷報告"""
        print("="*80)
        print("🚀 日期過濾問題診斷報告")
        print("="*80)
        
        try:
            # 1. 分析 MSSQL 邏輯
            self.check_mssql_date_logic()
            
            # 2. 分析 ClickHouse Silver 邏輯
            self.check_clickhouse_silver_date_logic()
            
            # 3. 比較不同過濾方式
            filter_results = self.compare_date_filtering_results()
            
            # 4. 分析時間分佈
            time_df = self.analyze_task_time_distribution()
            
            # 5. 檢查特定任務時間
            specific_df = self.check_specific_task_times()
            
            # 6. 找出額外任務
            extra_df, stats_df = self.find_extra_tasks()
            
            # 產生總結
            print("\n" + "="*80)
            print("📊 診斷總結")
            print("="*80)
            
            print("日期過濾方式比較:")
            for method, record_count, unique_tasks in filter_results:
                if record_count != "ERROR":
                    print(f"  {method}: {record_count} 筆記錄, {unique_tasks} 個任務")
            
            print(f"\n問題分析:")
            print(f"- MSSQL 使用 OR 邏輯檢查 START_TIME_, CLAIM_TIME_, END_TIME_")
            print(f"- ClickHouse Silver 只檢查 task_create_time (START_TIME_)")
            print(f"- 這導致 ClickHouse 包含了更多在 2025-12-25 創建的任務")
            print(f"- 但這些任務可能不符合 MSSQL 的完整過濾條件")
            
            if len(extra_df) > 0:
                print(f"\n額外任務特徵:")
                print(f"- 共有 {188 - 5} 筆額外任務")
                print(f"- 這些任務都在 2025-12-25 創建，但可能不符合 MSSQL 的其他條件")
            
        except Exception as e:
            print(f"❌ 診斷過程發生錯誤: {str(e)}")
            raise
        finally:
            self.ch_client.close()

if __name__ == "__main__":
    diagnostic = DateFilterDiagnostic()
    diagnostic.generate_diagnostic_report()