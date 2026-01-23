#!/usr/bin/env python3
"""
驗證 BPM 與 MDM 表對應關係
確認 V1/V2/V3 任務的維度資料來源
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def check_bpm_identitylink(client):
    """檢查 BPM 身份連結表"""
    print("🔍 檢查 BPM 身份連結表...")
    print("="*50)
    
    try:
        # 檢查 identitylink 表是否存在
        result = client.query("SELECT COUNT(*) FROM bronze.bpm_act_hi_identitylink")
        count = result.result_rows[0][0]
        print(f"✅ bronze.bpm_act_hi_identitylink: {count:,} 筆")
        
        # 檢查表結構
        structure = client.query("DESCRIBE bronze.bpm_act_hi_identitylink")
        columns = [row[0] for row in structure.result_rows]
        print(f"   欄位: {', '.join(columns)}")
        
        # 檢查與任務的關聯
        sample = client.query("""
        SELECT TASK_ID_, USER_ID_, TYPE_ 
        FROM bronze.bpm_act_hi_identitylink 
        WHERE TASK_ID_ IS NOT NULL 
        LIMIT 5
        """)
        print(f"   任務關聯範例: {len(sample.result_rows)} 筆")
        
    except Exception as e:
        print(f"❌ bronze.bpm_act_hi_identitylink: {e}")

def analyze_vx_dimension_coverage(client):
    """分析 V1/V2/V3 任務的維度覆蓋率"""
    print("\n🔍 分析 V1/V2/V3 任務維度覆蓋率...")
    print("="*50)
    
    try:
        # 分析各 Vx 類型的任務數量
        vx_analysis = client.query("""
        SELECT 
            CASE 
                WHEN TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                WHEN TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                ELSE 'Other'
            END AS vx_type,
            COUNT(*) as task_count
        FROM bronze.bpm_act_hi_taskinst
        WHERE TASK_DEF_KEY_ IS NOT NULL
        GROUP BY vx_type
        ORDER BY task_count DESC
        """)
        
        print("Vx 類型分布:")
        for row in vx_analysis.result_rows:
            vx_type, count = row
            print(f"   {vx_type}: {count:,} 筆")
        
        # 檢查 V1 任務在 varinst 中的覆蓋率
        v1_varinst_coverage = client.query("""
        SELECT 
            COUNT(DISTINCT t.ID_) as total_v1_tasks,
            COUNT(DISTINCT v.PROC_INST_ID_) as v1_with_varinst,
            round(COUNT(DISTINCT v.PROC_INST_ID_) * 100.0 / COUNT(DISTINCT t.ID_), 2) as coverage_pct
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN bronze.bpm_act_hi_varinst v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        WHERE t.TASK_DEF_KEY_ LIKE 'V1%'
        """)
        
        if v1_varinst_coverage.result_rows:
            total, with_varinst, coverage = v1_varinst_coverage.result_rows[0]
            print(f"\nV1 任務 varinst 覆蓋率:")
            print(f"   總 V1 任務: {total:,}")
            print(f"   有 varinst 的: {with_varinst:,}")
            print(f"   覆蓋率: {coverage}%")
        
        # 檢查 V2/V3 任務在 varinst 中的覆蓋率
        for vx in ['V2', 'V3']:
            vx_varinst_coverage = client.query(f"""
            SELECT 
                COUNT(DISTINCT t.ID_) as total_tasks,
                COUNT(DISTINCT v.PROC_INST_ID_) as with_varinst,
                round(COUNT(DISTINCT v.PROC_INST_ID_) * 100.0 / COUNT(DISTINCT t.ID_), 2) as coverage_pct
            FROM bronze.bpm_act_hi_taskinst t
            LEFT JOIN bronze.bpm_act_hi_varinst v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
            WHERE t.TASK_DEF_KEY_ LIKE '{vx}%'
            """)
            
            if vx_varinst_coverage.result_rows:
                total, with_varinst, coverage = vx_varinst_coverage.result_rows[0]
                print(f"\n{vx} 任務 varinst 覆蓋率:")
                print(f"   總 {vx} 任務: {total:,}")
                print(f"   有 varinst 的: {with_varinst:,}")
                print(f"   覆蓋率: {coverage}%")
        
    except Exception as e:
        print(f"❌ 維度覆蓋率分析失敗: {e}")

def check_manufacturing_dimensions_in_varinst(client):
    """檢查 varinst 中的製造維度變數"""
    print("\n🔍 檢查 varinst 中的製造維度變數...")
    print("="*50)
    
    try:
        # 檢查製造維度相關變數
        dimension_vars = client.query("""
        SELECT 
            NAME_,
            COUNT(*) as count,
            COUNT(DISTINCT PROC_INST_ID_) as unique_processes
        FROM bronze.bpm_act_hi_varinst
        WHERE NAME_ IN ('plant', 'factory', 'lineName', 'Plant', 'Factory', 'LineName')
        GROUP BY NAME_
        ORDER BY count DESC
        """)
        
        print("製造維度變數分布:")
        for row in dimension_vars.result_rows:
            name, count, unique_processes = row
            print(f"   {name}: {count:,} 筆 ({unique_processes:,} 個流程)")
        
        # 檢查製造維度變數的範例值
        sample_values = client.query("""
        SELECT NAME_, TEXT_, PROC_INST_ID_
        FROM bronze.bpm_act_hi_varinst
        WHERE NAME_ IN ('plant', 'factory', 'lineName') 
          AND TEXT_ IS NOT NULL 
          AND TEXT_ != ''
        LIMIT 10
        """)
        
        print(f"\n製造維度變數範例值:")
        for row in sample_values.result_rows:
            name, value, proc_id = row
            print(f"   {name}: {value} (流程: {proc_id})")
        
    except Exception as e:
        print(f"❌ 製造維度變數檢查失敗: {e}")

def validate_mdm_mapping_potential(client):
    """驗證 MDM 對應潛力"""
    print("\n🔍 驗證 MDM 對應潛力...")
    print("="*50)
    
    try:
        # 檢查 varinst 中的 lineName 與 MDM Line 的對應
        line_mapping = client.query("""
        SELECT 
            v.TEXT_ as varinst_line,
            COUNT(*) as varinst_count,
            COUNT(DISTINCT mdm.LINE_NAME) as mdm_matches
        FROM bronze.bpm_act_hi_varinst v
        LEFT JOIN bronze.common_mdm_line_desc_master mdm ON v.TEXT_ = mdm.LINE_NAME
        WHERE v.NAME_ = 'lineName' 
          AND v.TEXT_ IS NOT NULL 
          AND v.TEXT_ != ''
        GROUP BY v.TEXT_
        ORDER BY varinst_count DESC
        LIMIT 10
        """)
        
        print("varinst lineName 與 MDM Line 對應:")
        total_varinst_lines = 0
        matched_lines = 0
        
        for row in line_mapping.result_rows:
            varinst_line, varinst_count, mdm_matches = row
            total_varinst_lines += varinst_count
            if mdm_matches > 0:
                matched_lines += varinst_count
            status = "✅" if mdm_matches > 0 else "❌"
            print(f"   {status} {varinst_line}: {varinst_count} 筆 varinst, {mdm_matches} 筆 MDM 匹配")
        
        if total_varinst_lines > 0:
            match_rate = (matched_lines / total_varinst_lines) * 100
            print(f"\n整體對應成功率: {match_rate:.1f}% ({matched_lines}/{total_varinst_lines})")
        
        # 檢查 MDM 五階維度表的完整性
        mdm_completeness = client.query("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN region_code != '' THEN 1 END) as with_region,
            COUNT(CASE WHEN plant_code != '' THEN 1 END) as with_plant,
            COUNT(CASE WHEN factory_code != '' THEN 1 END) as with_factory,
            COUNT(CASE WHEN line_name != '' THEN 1 END) as with_line
        FROM silver.dim_mfg_five_level
        """)
        
        if mdm_completeness.result_rows:
            total, region, plant, factory, line = mdm_completeness.result_rows[0]
            print(f"\nMDM 五階維度表完整性:")
            print(f"   總記錄: {total:,}")
            print(f"   Region: {region:,} ({region/total*100:.1f}%)")
            print(f"   Plant: {plant:,} ({plant/total*100:.1f}%)")
            print(f"   Factory: {factory:,} ({factory/total*100:.1f}%)")
            print(f"   Line: {line:,} ({line/total*100:.1f}%)")
        
    except Exception as e:
        print(f"❌ MDM 對應潛力驗證失敗: {e}")

def main():
    """主執行函數"""
    try:
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 執行各項檢查
        check_bpm_identitylink(client)
        analyze_vx_dimension_coverage(client)
        check_manufacturing_dimensions_in_varinst(client)
        validate_mdm_mapping_potential(client)
        
        print("\n✅ BPM 與 MDM 對應關係驗證完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 執行過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)