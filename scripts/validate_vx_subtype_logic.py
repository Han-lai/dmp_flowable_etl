#!/usr/bin/env python3
"""
V1 子類型驗證腳本

驗證 V1 任務是否正確區分為：
- V1_NPE：工單號符合規則 + business_key 包含 "NPE"
- V1_MFG：工單號符合規則 + business_key 不包含 "NPE"
"""

import clickhouse_connect
from datetime import datetime
import sys

CLICKHOUSE_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def validate_v1_subtype():
    """驗證 V1 子類型邏輯"""
    print("\n" + "="*80)
    print("【驗證】V1 子類型邏輯（V1_NPE vs V1_MFG）")
    print("="*80)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        print("\n【檢查 1】工單號規則任務的 Vx 子類型分布")
        print("-" * 80)
        
        # 查詢工單號符合規則的任務及其子類型
        sql = """
        SELECT 
            vx_type,
            vx_subtype,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (
                SELECT COUNT(*) FROM silver.FACT_TASK_VX_ATTRIBUTION
                WHERE mo_number LIKE '196%' OR mo_number LIKE '199%' 
                   OR mo_number LIKE '200%' OR mo_number LIKE '210%'
                   OR mo_number LIKE '212%' OR mo_number LIKE '213%'
                   OR mo_number LIKE '315%'
            ), 2) as percentage
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE mo_number LIKE '196%' OR mo_number LIKE '199%' 
           OR mo_number LIKE '200%' OR mo_number LIKE '210%'
           OR mo_number LIKE '212%' OR mo_number LIKE '213%'
           OR mo_number LIKE '315%'
        GROUP BY vx_type, vx_subtype
        ORDER BY vx_type, vx_subtype
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        print(f"✓ 工單號規則任務的 Vx 類型分布：")
        for vx_type, vx_subtype, count, pct in rows:
            print(f"  {vx_type} / {vx_subtype}: {count} 筆 ({pct}%)")
        
        # 檢查是否所有工單號規則任務都是 V1
        sql_check = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN vx_type = 'V1' THEN 1 ELSE 0 END) as v1_count,
            SUM(CASE WHEN vx_type != 'V1' THEN 1 ELSE 0 END) as non_v1_count
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE mo_number LIKE '196%' OR mo_number LIKE '199%' 
           OR mo_number LIKE '200%' OR mo_number LIKE '210%'
           OR mo_number LIKE '212%' OR mo_number LIKE '213%'
           OR mo_number LIKE '315%'
        """
        
        result = client.query(sql_check)
        rows = result.result_rows
        
        if rows:
            total, v1_count, non_v1_count = rows[0]
            print(f"\n✓ 工單號規則任務總數：{total}")
            print(f"  V1 任務數：{v1_count}")
            print(f"  非 V1 任務數：{non_v1_count}")
            
            if non_v1_count > 0:
                print(f"\n  ⚠️ 發現 {non_v1_count} 筆非 V1 任務，應該都是 V1")
                return False
            else:
                print(f"\n  ✅ 所有工單號規則任務都被正確歸類為 V1")
        
        print("\n【檢查 2】V1_NPE 和 V1_MFG 的分布")
        print("-" * 80)
        
        sql = """
        SELECT 
            vx_subtype,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (
                SELECT COUNT(*) FROM silver.FACT_TASK_VX_ATTRIBUTION
                WHERE vx_type = 'V1'
            ), 2) as percentage
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE vx_type = 'V1'
        GROUP BY vx_subtype
        ORDER BY vx_subtype
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        print(f"✓ V1 任務的子類型分布：")
        v1_npe_count = 0
        v1_mfg_count = 0
        
        for subtype, count, pct in rows:
            print(f"  {subtype}: {count} 筆 ({pct}%)")
            if subtype == 'V1_NPE':
                v1_npe_count = count
            elif subtype == 'V1_MFG':
                v1_mfg_count = count
        
        print(f"\n  驗證：V1_NPE ({v1_npe_count}) + V1_MFG ({v1_mfg_count}) = {v1_npe_count + v1_mfg_count}")
        
        # 查詢 V1 任務總數
        sql_v1_total = """
        SELECT COUNT(*) as total FROM silver.FACT_TASK_VX_ATTRIBUTION WHERE vx_type = 'V1'
        """
        
        result = client.query(sql_v1_total)
        v1_total = result.result_rows[0][0]
        
        print(f"  V1 任務總數：{v1_total}")
        
        if v1_npe_count + v1_mfg_count != v1_total:
            print(f"\n  ⚠️ V1_NPE + V1_MFG 不等於 V1 總數，差異：{v1_total - (v1_npe_count + v1_mfg_count)}")
            return False
        else:
            print(f"\n  ✅ V1_NPE + V1_MFG = V1 總數，驗證通過")
        
        print("\n【檢查 3】V1_NPE 任務是否都包含 'NPE' 在 business_key 中")
        print("-" * 80)
        
        sql = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN business_key LIKE '%NPE%' THEN 1 ELSE 0 END) as with_npe,
            SUM(CASE WHEN business_key NOT LIKE '%NPE%' THEN 1 ELSE 0 END) as without_npe
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE vx_subtype = 'V1_NPE'
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, with_npe, without_npe = rows[0]
            print(f"✓ V1_NPE 任務總數：{total}")
            print(f"  business_key 包含 'NPE'：{with_npe}")
            print(f"  business_key 不包含 'NPE'：{without_npe}")
            
            if without_npe > 0:
                print(f"\n  ⚠️ 發現 {without_npe} 筆 V1_NPE 任務的 business_key 不包含 'NPE'")
                return False
            else:
                print(f"\n  ✅ 所有 V1_NPE 任務的 business_key 都包含 'NPE'")
        
        print("\n【檢查 4】V1_MFG 任務是否都不包含 'NPE' 在 business_key 中")
        print("-" * 80)
        
        sql = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN business_key LIKE '%NPE%' THEN 1 ELSE 0 END) as with_npe,
            SUM(CASE WHEN business_key NOT LIKE '%NPE%' THEN 1 ELSE 0 END) as without_npe
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE vx_subtype = 'V1_MFG'
        """
        
        result = client.query(sql)
        rows = result.result_rows
        
        if rows:
            total, with_npe, without_npe = rows[0]
            print(f"✓ V1_MFG 任務總數：{total}")
            print(f"  business_key 包含 'NPE'：{with_npe}")
            print(f"  business_key 不包含 'NPE'：{without_npe}")
            
            if with_npe > 0:
                print(f"\n  ⚠️ 發現 {with_npe} 筆 V1_MFG 任務的 business_key 包含 'NPE'")
                return False
            else:
                print(f"\n  ✅ 所有 V1_MFG 任務的 business_key 都不包含 'NPE'")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 驗證失敗：{str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*80)
    print("V1 子類型邏輯驗證 - 開始執行")
    print("="*80)
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    result = validate_v1_subtype()
    
    # 總結
    print("\n" + "="*80)
    print("驗證結果")
    print("="*80)
    print(f"整體結果：{'✅ V1 子類型邏輯驗證通過' if result else '❌ V1 子類型邏輯驗證失敗'}")
    print("="*80)
    
    return 0 if result else 1


if __name__ == '__main__':
    sys.exit(main())
