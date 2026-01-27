#!/usr/bin/env python3
"""
驗證 bronze.common_flowable_task_stats 欄位來源追溯
"""

import clickhouse_connect
import pandas as pd
from datetime import datetime

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def validate_basic_fields(client):
    """驗證基本欄位對應"""
    print("🔍 驗證基本欄位對應")
    print("="*50)
    
    try:
        # 從 flowable_task_stats 取樣本
        sample_query = """
        SELECT TaskId, ProcessInstanceId, TaskDefinitionKey, TaskStatus,
               TaskCreateTime, TaskClaimTime, TaskEndTime,
               TaskAssigneeName, TaskAssigneeAccount
        FROM bronze.common_flowable_task_stats 
        WHERE TaskId IS NOT NULL 
        LIMIT 5
        """
        
        result = client.query(sample_query)
        samples = result.result_rows
        
        print("📊 FlowableTaskStats 樣本:")
        for i, sample in enumerate(samples):
            print(f"\n樣本 {i+1}:")
            print(f"  TaskId: {sample[0]}")
            print(f"  ProcessInstanceId: {sample[1]}")
            print(f"  TaskDefinitionKey: {sample[2]}")
            print(f"  TaskStatus: {sample[3]}")
            print(f"  TaskCreateTime: {sample[4]}")
            print(f"  TaskClaimTime: {sample[5]}")
            print(f"  TaskEndTime: {sample[6]}")
            print(f"  TaskAssigneeName: {sample[7]}")
            print(f"  TaskAssigneeAccount: {sample[8]}")
            
            # 驗證第一個樣本
            if i == 0:
                task_id = sample[0]
                validate_single_task(client, task_id, sample)
                
    except Exception as e:
        print(f"❌ 基本欄位驗證失敗: {e}")

def validate_single_task(client, task_id, original_sample):
    """驗證單一任務的欄位對應"""
    print(f"\n🔍 驗證 TaskId={task_id} 的欄位對應:")
    
    try:
        # 查詢 ACT_HI_TASKINST
        native_query = """
        SELECT ID_, PROC_INST_ID_, TASK_DEF_KEY_, NAME_, ASSIGNEE_,
               START_TIME_, CLAIM_TIME_, END_TIME_,
               CASE 
                   WHEN END_TIME_ IS NOT NULL THEN 'DONE'
                   WHEN ASSIGNEE_ IS NOT NULL AND ASSIGNEE_ != '' THEN 'DOING' 
                   ELSE 'TODO'
               END as derived_status
        FROM bronze.bpm_act_hi_taskinst 
        WHERE ID_ = %s
        """
        
        result = client.query(native_query, [task_id])
        
        if result.result_rows:
            native_row = result.result_rows[0]
            print("✅ 在 ACT_HI_TASKINST 找到對應記錄:")
            print(f"  ID_: {native_row[0]} {'✅' if native_row[0] == original_sample[0] else '❌'}")
            print(f"  PROC_INST_ID_: {native_row[1]} {'✅' if native_row[1] == original_sample[1] else '❌'}")
            print(f"  TASK_DEF_KEY_: {native_row[2]} {'✅' if native_row[2] == original_sample[2] else '❌'}")
            print(f"  NAME_: {native_row[3]}")
            print(f"  ASSIGNEE_: {native_row[4]} {'✅' if native_row[4] == original_sample[8] else '❌'}")
            print(f"  START_TIME_: {native_row[5]} {'✅' if native_row[5] == original_sample[4] else '❌'}")
            print(f"  CLAIM_TIME_: {native_row[6]} {'✅' if native_row[6] == original_sample[5] else '❌'}")
            print(f"  END_TIME_: {native_row[7]} {'✅' if native_row[7] == original_sample[6] else '❌'}")
            print(f"  推導狀態: {native_row[8]} {'✅' if native_row[8] == original_sample[3] else '❌'}")
            
            # 如果有 ASSIGNEE_，查詢員工姓名
            if native_row[4]:
                validate_employee_name(client, native_row[4], original_sample[7])
                
        else:
            print("❌ 在 ACT_HI_TASKINST 中找不到對應記錄")
            
    except Exception as e:
        print(f"❌ 單一任務驗證失敗: {e}")

def validate_employee_name(client, emp_code, expected_name):
    """驗證員工姓名對應"""
    try:
        emp_query = """
        SELECT EmpCode, EmpName 
        FROM bronze.common_hr_employee 
        WHERE EmpCode = %s
        """
        
        result = client.query(emp_query, [emp_code])
        
        if result.result_rows:
            emp_row = result.result_rows[0]
            actual_name = emp_row[1]
            print(f"  員工姓名: {actual_name} {'✅' if actual_name == expected_name else '❌'}")
        else:
            print(f"  ❌ 員工代碼 {emp_code} 在 HR 表中找不到")
            
    except Exception as e:
        print(f"❌ 員工姓名驗證失敗: {e}")

def validate_variables(client):
    """驗證變數欄位對應"""
    print("\n🔍 驗證變數欄位對應")
    print("="*40)
    
    try:
        # 取有變數的樣本
        sample_query = """
        SELECT TaskId, ProcessInstanceId, Plant, Factory, Line, MoNumber
        FROM bronze.common_flowable_task_stats 
        WHERE ProcessInstanceId IS NOT NULL 
          AND Plant IS NOT NULL
        LIMIT 3
        """
        
        result = client.query(sample_query)
        samples = result.result_rows
        
        for i, sample in enumerate(samples):
            print(f"\n樣本 {i+1}:")
            task_id = sample[0]
            proc_inst_id = sample[1]
            expected_plant = sample[2]
            expected_factory = sample[3]
            expected_line = sample[4]
            expected_mo = sample[5]
            
            print(f"  TaskId: {task_id}")
            print(f"  ProcessInstanceId: {proc_inst_id}")
            print(f"  期望 Plant: {expected_plant}")
            print(f"  期望 Factory: {expected_factory}")
            print(f"  期望 Line: {expected_line}")
            print(f"  期望 MoNumber: {expected_mo}")
            
            # 查詢變數
            var_query = """
            SELECT NAME_, TEXT_, LONG_, DOUBLE_
            FROM bronze.bpm_act_hi_varinst 
            WHERE PROC_INST_ID_ = %s
              AND NAME_ IN ('plant', 'factory', 'lineName', 'moNumber')
            ORDER BY NAME_
            """
            
            var_result = client.query(var_query, [proc_inst_id])
            
            print("  ACT_HI_VARINST 變數:")
            var_dict = {}
            for var_row in var_result.result_rows:
                var_name = var_row[0]
                var_value = var_row[1] or var_row[2] or var_row[3]
                var_dict[var_name] = var_value
                print(f"    {var_name}: {var_value}")
            
            # 比對結果
            print("  比對結果:")
            if 'plant' in var_dict:
                print(f"    Plant: {var_dict['plant']} {'✅' if var_dict['plant'] == expected_plant else '❌'}")
            if 'factory' in var_dict:
                print(f"    Factory: {var_dict['factory']} {'✅' if var_dict['factory'] == expected_factory else '❌'}")
            if 'lineName' in var_dict:
                print(f"    Line: {var_dict['lineName']} {'✅' if var_dict['lineName'] == expected_line else '❌'}")
            if 'moNumber' in var_dict:
                print(f"    MoNumber: {var_dict['moNumber']} {'✅' if var_dict['moNumber'] == expected_mo else '❌'}")
                
    except Exception as e:
        print(f"❌ 變數驗證失敗: {e}")

def validate_pivot_table(client):
    """驗證 silver.mv_varinst_pivoted 表"""
    print("\n🔍 驗證 silver.mv_varinst_pivoted 表")
    print("="*45)
    
    try:
        # 取樣本比對
        sample_query = """
        SELECT ProcessInstanceId, Plant, Factory, Line, MoNumber
        FROM bronze.common_flowable_task_stats 
        WHERE ProcessInstanceId IS NOT NULL 
          AND Plant IS NOT NULL
        LIMIT 3
        """
        
        result = client.query(sample_query)
        samples = result.result_rows
        
        for i, sample in enumerate(samples):
            proc_inst_id = sample[0]
            expected_plant = sample[1]
            expected_factory = sample[2]
            expected_line = sample[3]
            expected_mo = sample[4]
            
            print(f"\n樣本 {i+1} (PROC_INST_ID={proc_inst_id}):")
            
            # 查詢 pivot 表
            pivot_query = """
            SELECT varinst_plant, varinst_factory, varinst_lineName, varinst_moNumber
            FROM silver.mv_varinst_pivoted 
            WHERE PROC_INST_ID_ = %s
            """
            
            pivot_result = client.query(pivot_query, [proc_inst_id])
            
            if pivot_result.result_rows:
                pivot_row = pivot_result.result_rows[0]
                print(f"  Pivot Plant: {pivot_row[0]} {'✅' if pivot_row[0] == expected_plant else '❌'}")
                print(f"  Pivot Factory: {pivot_row[1]} {'✅' if pivot_row[1] == expected_factory else '❌'}")
                print(f"  Pivot LineName: {pivot_row[2]} {'✅' if pivot_row[2] == expected_line else '❌'}")
                print(f"  Pivot MoNumber: {pivot_row[3]} {'✅' if pivot_row[3] == expected_mo else '❌'}")
            else:
                print("  ❌ 在 silver.mv_varinst_pivoted 中找不到對應記錄")
                
    except Exception as e:
        print(f"❌ Pivot 表驗證失敗: {e}")

def validate_status_logic(client):
    """驗證 TaskStatus 推導邏輯"""
    print("\n🔍 驗證 TaskStatus 推導邏輯")
    print("="*40)
    
    try:
        # 統計各狀態分佈
        stats_query = """
        SELECT 
            TaskStatus,
            COUNT(*) as count
        FROM bronze.common_flowable_task_stats
        GROUP BY TaskStatus
        ORDER BY count DESC
        """
        
        result = client.query(stats_query)
        
        print("📊 FlowableTaskStats 狀態分佈:")
        for row in result.result_rows:
            print(f"  {row[0]}: {row[1]:,}")
        
        # 驗證推導邏輯
        validation_query = """
        WITH native_status AS (
            SELECT 
                ID_,
                CASE 
                    WHEN END_TIME_ IS NOT NULL THEN 'DONE'
                    WHEN ASSIGNEE_ IS NOT NULL AND ASSIGNEE_ != '' THEN 'DOING' 
                    ELSE 'TODO'
                END as derived_status
            FROM bronze.bpm_act_hi_taskinst
        ),
        flowable_status AS (
            SELECT TaskId, TaskStatus
            FROM bronze.common_flowable_task_stats
            WHERE TaskId IS NOT NULL
        )
        SELECT 
            f.TaskStatus as flowable_status,
            n.derived_status,
            COUNT(*) as count
        FROM flowable_status f
        JOIN native_status n ON f.TaskId = n.ID_
        GROUP BY f.TaskStatus, n.derived_status
        ORDER BY count DESC
        """
        
        validation_result = client.query(validation_query)
        
        print("\n📊 狀態邏輯驗證:")
        print("  FlowableTaskStats vs 推導狀態:")
        for row in validation_result.result_rows:
            match_status = "✅" if row[0] == row[1] else "❌"
            print(f"  {row[0]} vs {row[1]}: {row[2]:,} {match_status}")
            
    except Exception as e:
        print(f"❌ 狀態邏輯驗證失敗: {e}")

def main():
    """主執行函數"""
    print("🔍 bronze.common_flowable_task_stats 欄位來源驗證")
    print("="*60)
    
    client = get_clickhouse_client()
    if client is None:
        return
    
    try:
        # 執行各項驗證
        validate_basic_fields(client)
        validate_variables(client)
        validate_pivot_table(client)
        validate_status_logic(client)
        
        print("\n" + "="*60)
        print("📋 驗證總結")
        print("="*60)
        print("✅ 已完成所有欄位來源驗證")
        print("📊 驗證項目:")
        print("  - 基本欄位對應 (TaskId, ProcessInstanceId, TaskDefinitionKey 等)")
        print("  - 時間欄位對應 (TaskCreateTime, TaskClaimTime, TaskEndTime)")
        print("  - 人員資訊對應 (TaskAssigneeName, TaskAssigneeAccount)")
        print("  - 變數欄位對應 (Plant, Factory, Line, MoNumber)")
        print("  - TaskStatus 推導邏輯")
        print("  - silver.mv_varinst_pivoted 表一致性")
        
    except Exception as e:
        print(f"❌ 驗證過程發生錯誤: {e}")
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    main()