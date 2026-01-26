#!/usr/bin/env python3
"""
分析 ClickHouse 表格的 ORDER BY 設計問題
檢查哪些表格使用了不當的 ORDER BY tuple() 設計
"""

import clickhouse_connect
import sys
from datetime import datetime

def connect_clickhouse():
    """連接到 ClickHouse"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ 連接 ClickHouse 失敗: {e}")
        return None

def analyze_table_order_by(client):
    """分析所有表格的 ORDER BY 設計"""
    print("🔍 分析所有 Bronze 層表格的 ORDER BY 設計...")
    
    try:
        # 取得所有表格的建立語句
        query = """
        SELECT 
            database,
            name as table_name,
            engine,
            create_table_query
        FROM system.tables 
        WHERE database = 'bronze'
          AND engine LIKE '%MergeTree%'
        ORDER BY name
        """
        
        result = client.query(query)
        
        if not result.result_rows:
            print("⚠️  沒有找到 MergeTree 表格")
            return {}
            
        print(f"\n📊 找到 {len(result.result_rows)} 個 MergeTree 表格:")
        
        order_by_analysis = {
            'tuple_empty': [],      # ORDER BY tuple()
            'single_column': [],    # ORDER BY (column)
            'multi_column': [],     # ORDER BY (col1, col2)
            'time_based': [],       # ORDER BY 包含時間欄位
            'problematic': []       # 有問題的設計
        }
        
        print("表格名稱".ljust(35) + "ORDER BY 設計".ljust(40) + "狀態")
        print("-" * 85)
        
        for row in result.result_rows:
            database, table_name, engine, create_query = row
            
            # 解析 ORDER BY 子句
            order_by_clause = extract_order_by(create_query)
            
            # 分析 ORDER BY 設計
            analysis_result = analyze_order_by_clause(order_by_clause)
            
            # 分類
            if 'tuple()' in order_by_clause:
                order_by_analysis['tuple_empty'].append(table_name)
                status = "❌ 效能差"
            elif analysis_result['is_time_based']:
                order_by_analysis['time_based'].append(table_name)
                status = "✅ 時間索引"
            elif analysis_result['column_count'] > 1:
                order_by_analysis['multi_column'].append(table_name)
                status = "✅ 複合索引"
            elif analysis_result['column_count'] == 1:
                order_by_analysis['single_column'].append(table_name)
                status = "🟡 單一索引"
            else:
                order_by_analysis['problematic'].append(table_name)
                status = "❌ 有問題"
            
            # 顯示結果
            order_by_display = order_by_clause[:38] + "..." if len(order_by_clause) > 38 else order_by_clause
            print(f"{table_name.ljust(33)} {order_by_display.ljust(38)} {status}")
        
        return order_by_analysis
        
    except Exception as e:
        print(f"❌ 分析失敗: {e}")
        return {}

def extract_order_by(create_query):
    """從 CREATE TABLE 語句中提取 ORDER BY 子句"""
    try:
        # 尋找 ORDER BY 關鍵字
        order_by_start = create_query.upper().find('ORDER BY')
        if order_by_start == -1:
            return "無 ORDER BY"
        
        # 從 ORDER BY 開始提取
        remaining = create_query[order_by_start + 8:].strip()
        
        # 尋找下一個關鍵字 (PARTITION BY, SETTINGS, etc.)
        keywords = ['PARTITION BY', 'SETTINGS', 'TTL', 'SAMPLE BY']
        end_pos = len(remaining)
        
        for keyword in keywords:
            pos = remaining.upper().find(keyword)
            if pos != -1 and pos < end_pos:
                end_pos = pos
        
        order_by_clause = remaining[:end_pos].strip()
        
        # 移除尾部的逗號或括號
        order_by_clause = order_by_clause.rstrip(',)')
        
        return order_by_clause
        
    except Exception as e:
        return f"解析錯誤: {e}"

def analyze_order_by_clause(order_by_clause):
    """分析 ORDER BY 子句的特性"""
    analysis = {
        'column_count': 0,
        'is_time_based': False,
        'has_id_column': False,
        'columns': []
    }
    
    if not order_by_clause or order_by_clause == "無 ORDER BY":
        return analysis
    
    # 移除括號並分割欄位
    clause_clean = order_by_clause.strip('()')
    
    if 'tuple()' in clause_clean:
        return analysis
    
    # 分割欄位 (簡單處理，不考慮複雜的函數)
    columns = [col.strip() for col in clause_clean.split(',')]
    analysis['columns'] = columns
    analysis['column_count'] = len(columns)
    
    # 檢查是否包含時間欄位
    time_keywords = ['time', 'date', 'sync', 'create', 'update', 'start', 'end']
    for col in columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in time_keywords):
            analysis['is_time_based'] = True
            break
    
    # 檢查是否包含 ID 欄位
    id_keywords = ['id', 'key', 'inst_id']
    for col in columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in id_keywords):
            analysis['has_id_column'] = True
            break
    
    return analysis

def suggest_order_by_improvements(client, problematic_tables):
    """為有問題的表格建議 ORDER BY 改進方案"""
    print(f"\n🔧 ORDER BY 改進建議:")
    
    # 特定表格的建議
    suggestions = {
        'common_flowable_task_stats': {
            'current': 'tuple()',
            'suggested': '(TaskId, TaskCreateTime)',
            'reason': '按任務ID和建立時間排序，提升查詢效能'
        },
        'bpm_act_hi_procinst': {
            'current': 'tuple()',
            'suggested': '(PROC_INST_ID_, START_TIME_)',
            'reason': '按流程實例ID和開始時間排序，符合業務查詢模式'
        },
        'bpm_act_hi_taskinst': {
            'current': 'tuple()',
            'suggested': '(PROC_INST_ID_, START_TIME_)',
            'reason': '按流程實例ID和開始時間排序，與流程實例表一致'
        },
        'bpm_act_hi_varinst': {
            'current': 'tuple()',
            'suggested': '(PROC_INST_ID_, CREATE_TIME_)',
            'reason': '按流程實例ID和建立時間排序，提升變數查詢效能'
        }
    }
    
    for table in problematic_tables:
        if table in suggestions:
            suggestion = suggestions[table]
            print(f"\n📋 {table}:")
            print(f"  目前: ORDER BY {suggestion['current']}")
            print(f"  建議: ORDER BY {suggestion['suggested']}")
            print(f"  原因: {suggestion['reason']}")
        else:
            print(f"\n📋 {table}:")
            print(f"  建議: 根據主要查詢模式設計 ORDER BY")
            print(f"  考慮: 主鍵欄位 + 時間欄位的組合")

def generate_alter_statements(problematic_tables):
    """產生 ALTER TABLE 語句來修正 ORDER BY"""
    print(f"\n📝 修正 SQL 語句:")
    
    alter_statements = {
        'common_flowable_task_stats': "ALTER TABLE bronze.common_flowable_task_stats MODIFY ORDER BY (TaskId, TaskCreateTime)",
        'bpm_act_hi_procinst': "ALTER TABLE bronze.bpm_act_hi_procinst MODIFY ORDER BY (PROC_INST_ID_, START_TIME_)",
        'bmp_act_hi_taskinst': "ALTER TABLE bronze.bmp_act_hi_taskinst MODIFY ORDER BY (PROC_INST_ID_, START_TIME_)",
        'bmp_act_hi_varinst': "ALTER TABLE bronze.bmp_act_hi_varinst MODIFY ORDER BY (PROC_INST_ID_, CREATE_TIME_)"
    }
    
    print("```sql")
    for table in problematic_tables:
        if table in alter_statements:
            print(f"-- 修正 {table}")
            print(alter_statements[table] + ";")
            print()
    print("```")

def main():
    """主函數"""
    print("=" * 80)
    print("📊 ClickHouse ORDER BY 效能分析工具")
    print("=" * 80)
    print(f"⏰ 分析時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 目標: 識別並修正不當的 ORDER BY 設計")
    
    # 連接 ClickHouse
    client = connect_clickhouse()
    if not client:
        sys.exit(1)
    
    # 分析 ORDER BY 設計
    analysis = analyze_table_order_by(client)
    
    if not analysis:
        print("❌ 分析失敗")
        sys.exit(1)
    
    # 統計報告
    print(f"\n📈 ORDER BY 設計統計:")
    print(f"  ❌ 使用 tuple(): {len(analysis['tuple_empty'])} 個表格")
    print(f"  ✅ 時間索引: {len(analysis['time_based'])} 個表格")
    print(f"  ✅ 複合索引: {len(analysis['multi_column'])} 個表格")
    print(f"  🟡 單一索引: {len(analysis['single_column'])} 個表格")
    print(f"  ❌ 有問題: {len(analysis['problematic'])} 個表格")
    
    # 詳細列表
    if analysis['tuple_empty']:
        print(f"\n❌ 使用 ORDER BY tuple() 的表格 (效能最差):")
        for table in analysis['tuple_empty']:
            print(f"  - {table}")
    
    if analysis['time_based']:
        print(f"\n✅ 使用時間索引的表格 (效能良好):")
        for table in analysis['time_based'][:5]:  # 只顯示前5個
            print(f"  - {table}")
        if len(analysis['time_based']) > 5:
            print(f"  ... 還有 {len(analysis['time_based']) - 5} 個")
    
    # 改進建議
    problematic_tables = analysis['tuple_empty'] + analysis['problematic']
    
    if problematic_tables:
        suggest_order_by_improvements(client, problematic_tables)
        generate_alter_statements(problematic_tables)
        
        print(f"\n⚠️  影響評估:")
        print("  - 查詢效能: ORDER BY tuple() 無法利用索引，查詢速度慢")
        print("  - 資料跳過: 無法根據條件跳過不相關的資料塊")
        print("  - 壓縮效率: 資料排序混亂，壓縮效果差")
        
        print(f"\n📝 修正步驟:")
        print("  1. 分析主要查詢模式")
        print("  2. 選擇合適的 ORDER BY 欄位組合")
        print("  3. 執行 ALTER TABLE MODIFY ORDER BY 語句")
        print("  4. 等待背景重新排序完成")
        print("  5. 驗證查詢效能改善")
        
        return 1
    else:
        print(f"\n🎉 所有表格的 ORDER BY 設計都很合理！")
        return 0

if __name__ == "__main__":
    sys.exit(main())