#!/usr/bin/env python3
"""
Silver 層資料膨脹問題診斷腳本
診斷為何 5 筆 Bronze 記錄變成 188 筆 Silver 記錄
"""

import clickhouse_connect
import pandas as pd
from datetime import datetime

class SilverLayerDiagnostic:
    def __init__(self):
        self.ch_client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        
        # 測試用的 5 個任務 ID
        self.test_task_ids = [
            '117c3488-e0aa-11f0-8766-badd3bc212ac',
            'a84b6195-e124-11f0-8766-badd3bc212ac', 
            'a8cf860b-e124-11f0-8766-badd3bc212ac',
            'a96360f1-e124-11f0-8766-badd3bc212ac',
            'dc9fb8e2-e155-11f0-8766-badd3bc212ac'
        ]
        
        self.test_proc_ids = [
            '1178d911-e0aa-11f0-8766-badd3bc212ac',
            'a83fa1af-e124-11f0-8766-badd3bc212ac',
            'a8c8a825-e124-11f0-8766-badd3bc212ac', 
            'a9607bab-e124-11f0-8766-badd3bc212ac',
            'dc9cab8e-e155-11f0-8766-badd3bc212ac'
        ]
    
    def check_bronze_layer_data(self):
        """檢查 Bronze 層基礎資料"""
        print("🔍 檢查 Bronze 層基礎資料")
        print("="*60)
        
        # 檢查任務表
        task_sql = f"""
        SELECT 
            'bpm_act_hi_taskinst' as table_name,
            COUNT(*) as total_records,
            COUNT(DISTINCT ID_) as unique_task_ids,
            COUNT(DISTINCT PROC_INST_ID_) as unique_proc_ids
        FROM bronze.bpm_act_hi_taskinst
        WHERE ID_ IN {tuple(self.test_task_ids)}
        """
        
        task_df = self.ch_client.query_df(task_sql)
        print("任務表統計:")
        print(task_df.to_string(index=False))
        
        # 檢查流程實例表
        proc_sql = f"""
        SELECT 
            'bpm_act_hi_procinst' as table_name,
            COUNT(*) as total_records,
            COUNT(DISTINCT PROC_INST_ID_) as unique_proc_ids
        FROM bronze.bpm_act_hi_procinst
        WHERE PROC_INST_ID_ IN {tuple(self.test_proc_ids)}
        """
        
        proc_df = self.ch_client.query_df(proc_sql)
        print("\n流程實例表統計:")
        print(proc_df.to_string(index=False))
        
        # 檢查變數表
        var_sql = f"""
        SELECT 
            'bpm_act_hi_varinst' as table_name,
            COUNT(*) as total_records,
            COUNT(DISTINCT PROC_INST_ID_) as unique_proc_ids,
            COUNT(DISTINCT NAME_) as unique_var_names
        FROM bronze.bpm_act_hi_varinst
        WHERE PROC_INST_ID_ IN {tuple(self.test_proc_ids)}
        """
        
        var_df = self.ch_client.query_df(var_sql)
        print("\n變數表統計:")
        print(var_df.to_string(index=False))
        
        return task_df, proc_df, var_df
    
    def check_varinst_pivoted_mview(self):
        """檢查 mv_varinst_pivoted 是否有重複"""
        print("\n🔍 檢查 mv_varinst_pivoted MVIEW")
        print("="*60)
        
        # 檢查重複的 PROC_INST_ID_
        duplicate_sql = f"""
        SELECT 
            PROC_INST_ID_,
            COUNT(*) as record_count
        FROM silver.mv_varinst_pivoted 
        WHERE PROC_INST_ID_ IN {tuple(self.test_proc_ids)}
        GROUP BY PROC_INST_ID_
        ORDER BY record_count DESC, PROC_INST_ID_
        """
        
        duplicate_df = self.ch_client.query_df(duplicate_sql)
        print("PROC_INST_ID_ 重複檢查:")
        print(duplicate_df.to_string(index=False))
        
        # 檢查具體內容
        content_sql = f"""
        SELECT 
            PROC_INST_ID_,
            varinst_plant,
            varinst_factory,
            varinst_lineName,
            varinst_moNumber,
            varinst_name
        FROM silver.mv_varinst_pivoted 
        WHERE PROC_INST_ID_ IN {tuple(self.test_proc_ids)}
        ORDER BY PROC_INST_ID_
        """
        
        content_df = self.ch_client.query_df(content_sql)
        print("\nmv_varinst_pivoted 內容:")
        print(content_df.to_string(index=False))
        
        return duplicate_df, content_df
    
    def check_hr_employee_duplicates(self):
        """檢查 HR_Employee 表是否有重複"""
        print("\n🔍 檢查 common_hr_employee 重複")
        print("="*60)
        
        # 先取得相關的 EmpCode
        empcode_sql = f"""
        SELECT DISTINCT ASSIGNEE_ as emp_code
        FROM bronze.bpm_act_hi_taskinst
        WHERE ID_ IN {tuple(self.test_task_ids)}
        AND ASSIGNEE_ IS NOT NULL AND ASSIGNEE_ != ''
        """
        
        empcode_df = self.ch_client.query_df(empcode_sql)
        emp_codes = empcode_df['emp_code'].tolist()
        
        if emp_codes:
            # 檢查重複
            duplicate_sql = f"""
            SELECT 
                EmpCode,
                COUNT(*) as record_count,
                groupArray(EmpName) as emp_names
            FROM bronze.common_hr_employee
            WHERE EmpCode IN {tuple(emp_codes)}
            GROUP BY EmpCode
            ORDER BY record_count DESC
            """
            
            duplicate_df = self.ch_client.query_df(duplicate_sql)
            print("EmpCode 重複檢查:")
            print(duplicate_df.to_string(index=False))
            return duplicate_df
        else:
            print("沒有找到相關的 EmpCode")
            return pd.DataFrame()
    
    def check_silver_mview_explosion(self):
        """檢查 Silver MVIEW 的資料膨脹"""
        print("\n🔍 檢查 Silver MVIEW 資料膨脹")
        print("="*60)
        
        # 檢查每個任務 ID 的記錄數
        explosion_sql = f"""
        SELECT 
            task_id,
            COUNT(*) as record_count,
            groupArray(DISTINCT plant) as plants,
            groupArray(DISTINCT factory) as factories,
            groupArray(DISTINCT line) as lines
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE task_id IN {tuple(self.test_task_ids)}
        GROUP BY task_id
        ORDER BY record_count DESC
        """
        
        explosion_df = self.ch_client.query_df(explosion_sql)
        print("每個任務 ID 的記錄數:")
        print(explosion_df.to_string(index=False))
        
        # 檢查具體的重複記錄
        if len(explosion_df) > 0:
            max_task_id = explosion_df.iloc[0]['task_id']
            detail_sql = f"""
            SELECT 
                task_id,
                proc_inst_id,
                plant,
                factory,
                line,
                task_status,
                vx_type,
                vx_subtype,
                task_assignee_account,
                task_assignee_name
            FROM silver.mv_fact_task_vx_attribution FINAL
            WHERE task_id = '{max_task_id}'
            ORDER BY plant, factory, line
            """
            
            detail_df = self.ch_client.query_df(detail_sql)
            print(f"\n任務 {max_task_id} 的詳細記錄:")
            print(detail_df.to_string(index=False))
            
            return explosion_df, detail_df
        
        return explosion_df, pd.DataFrame()
    
    def analyze_join_logic(self):
        """分析 JOIN 邏輯問題"""
        print("\n🔍 分析 JOIN 邏輯問題")
        print("="*60)
        
        # 模擬 MVIEW 的 JOIN 邏輯，逐步檢查
        step1_sql = f"""
        SELECT 
            'Step 1: Task + Process' as step,
            COUNT(*) as record_count
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN bronze.bpm_act_hi_procinst p 
            ON t.PROC_INST_ID_ = p.PROC_INST_ID_
        WHERE t.ID_ IN {tuple(self.test_task_ids)}
        """
        
        step2_sql = f"""
        SELECT 
            'Step 2: + Varinst Pivoted' as step,
            COUNT(*) as record_count
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN bronze.bmp_act_hi_procinst p 
            ON t.PROC_INST_ID_ = p.PROC_INST_ID_
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        WHERE t.ID_ IN {tuple(self.test_task_ids)}
        """
        
        step3_sql = f"""
        SELECT 
            'Step 3: + HR Employee' as step,
            COUNT(*) as record_count
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN bronze.bmp_act_hi_procinst p 
            ON t.PROC_INST_ID_ = p.PROC_INST_ID_
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        LEFT JOIN bronze.common_hr_employee he
            ON t.ASSIGNEE_ = he.EmpCode
        WHERE t.ID_ IN {tuple(self.test_task_ids)}
        """
        
        step4_sql = f"""
        SELECT 
            'Step 4: + Task Bypass' as step,
            COUNT(*) as record_count
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN bronze.bmp_act_hi_procinst p 
            ON t.PROC_INST_ID_ = p.PROC_INST_ID_
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        LEFT JOIN bronze.common_hr_employee he
            ON t.ASSIGNEE_ = he.EmpCode
        LEFT JOIN bronze.bpm_act_hi_varinst tb
            ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
        WHERE t.ID_ IN {tuple(self.test_task_ids)}
        """
        
        steps = [
            ("Step 1", step1_sql),
            ("Step 2", step2_sql), 
            ("Step 3", step3_sql),
            ("Step 4", step4_sql)
        ]
        
        results = []
        for step_name, sql in steps:
            try:
                df = self.ch_client.query_df(sql)
                record_count = df.iloc[0]['record_count']
                results.append((step_name, record_count))
                print(f"{step_name}: {record_count} 筆記錄")
            except Exception as e:
                print(f"{step_name}: 查詢失敗 - {e}")
                results.append((step_name, "ERROR"))
        
        return results
    
    def check_date_filter_logic(self):
        """檢查日期過濾邏輯"""
        print("\n🔍 檢查日期過濾邏輯")
        print("="*60)
        
        # 檢查 Silver MVIEW 中的日期過濾
        date_filter_sql = """
        SELECT 
            toDate(task_create_time) as task_date,
            COUNT(*) as record_count,
            COUNT(DISTINCT task_id) as unique_tasks
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE toDate(task_create_time) BETWEEN '2025-12-24' AND '2025-12-26'
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        GROUP BY task_date
        ORDER BY task_date
        """
        
        date_df = self.ch_client.query_df(date_filter_sql)
        print("按日期分組的記錄數:")
        print(date_df.to_string(index=False))
        
        return date_df
    
    def generate_diagnostic_report(self):
        """產生診斷報告"""
        print("\n" + "="*80)
        print("🚀 Silver 層資料膨脹診斷報告")
        print("="*80)
        
        try:
            # 1. Bronze 層檢查
            task_df, proc_df, var_df = self.check_bronze_layer_data()
            
            # 2. MVIEW 檢查
            duplicate_df, content_df = self.check_varinst_pivoted_mview()
            
            # 3. HR Employee 檢查
            hr_duplicate_df = self.check_hr_employee_duplicates()
            
            # 4. Silver MVIEW 膨脹檢查
            explosion_df, detail_df = self.check_silver_mview_explosion()
            
            # 5. JOIN 邏輯分析
            join_results = self.analyze_join_logic()
            
            # 6. 日期過濾檢查
            date_df = self.check_date_filter_logic()
            
            # 產生總結
            print("\n" + "="*80)
            print("📊 診斷總結")
            print("="*80)
            
            print(f"Bronze 層任務記錄: {task_df.iloc[0]['total_records']} 筆")
            print(f"Silver 層任務記錄: {explosion_df['record_count'].sum() if len(explosion_df) > 0 else 0} 筆")
            
            if len(duplicate_df) > 0:
                max_duplicates = duplicate_df['record_count'].max()
                if max_duplicates > 1:
                    print(f"⚠️  mv_varinst_pivoted 有重複記錄，最多 {max_duplicates} 筆")
                else:
                    print("✅ mv_varinst_pivoted 沒有重複記錄")
            
            if len(hr_duplicate_df) > 0:
                max_hr_duplicates = hr_duplicate_df['record_count'].max()
                if max_hr_duplicates > 1:
                    print(f"⚠️  common_hr_employee 有重複記錄，最多 {max_hr_duplicates} 筆")
                else:
                    print("✅ common_hr_employee 沒有重複記錄")
            
            print("\nJOIN 步驟記錄數變化:")
            for step_name, count in join_results:
                print(f"  {step_name}: {count}")
            
            # 找出問題步驟
            if len(join_results) >= 2:
                for i in range(1, len(join_results)):
                    prev_count = join_results[i-1][1]
                    curr_count = join_results[i][1]
                    if isinstance(prev_count, int) and isinstance(curr_count, int):
                        if curr_count > prev_count:
                            print(f"🚨 問題發生在 {join_results[i][0]}: 記錄數從 {prev_count} 增加到 {curr_count}")
            
        except Exception as e:
            print(f"❌ 診斷過程發生錯誤: {str(e)}")
            raise
        finally:
            self.ch_client.close()

if __name__ == "__main__":
    diagnostic = SilverLayerDiagnostic()
    diagnostic.generate_diagnostic_report()