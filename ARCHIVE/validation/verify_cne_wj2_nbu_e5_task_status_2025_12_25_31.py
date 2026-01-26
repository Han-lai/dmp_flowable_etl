#!/usr/bin/env python3
"""
驗證 CNE WJ2 NBU E5 在 2025-12-25 到 2025-12-31 各 V1、V2、V3 任務完成狀態
"""

import clickhouse_connect

def main():
    print("🔍 查詢 CNE WJ2 NBU E5 在 2025-12-25 到 2025-12-31 的任務完成狀態")
    print("=" * 70)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 查詢任務完成狀態
        query = """
        SELECT 
            task_create_date,
            vx_type,
            task_status,
            COUNT(*) as task_count
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE region = 'CNE'
          AND plant = 'WJ2' 
          AND factory = 'NBU'
          AND line = 'E5'
          AND task_create_date BETWEEN '2025-12-25' AND '2025-12-31'
          AND is_excluded = 0
          AND vx_type IN ('V1', 'V2', 'V3')
        GROUP BY task_create_date, vx_type, task_status
        ORDER BY task_create_date, vx_type, task_status
        """
        
        result = client.query(query)
        
        if result.result_rows:
            print("✅ 查詢結果:")
            print("日期         VX類型  狀態     數量")
            print("-" * 35)
            
            total_by_vx = {}
            total_by_status = {}
            daily_summary = {}
            
            for row in result.result_rows:
                date, vx_type, status, count = row
                print(f"{date} {vx_type:<6} {status:<8} {count:<6}")
                
                # 統計
                if vx_type not in total_by_vx:
                    total_by_vx[vx_type] = 0
                total_by_vx[vx_type] += count
                
                if status not in total_by_status:
                    total_by_status[status] = 0
                total_by_status[status] += count
                
                # 每日統計
                if date not in daily_summary:
                    daily_summary[date] = {}
                if vx_type not in daily_summary[date]:
                    daily_summary[date][vx_type] = {'TODO': 0, 'DOING': 0, 'DONE': 0}
                daily_summary[date][vx_type][status] = count
            
            print("\n📊 統計摘要:")
            print("按 VX 類型統計:")
            for vx_type, count in sorted(total_by_vx.items()):
                print(f"  {vx_type}: {count:,} 筆")
            
            print("\n按任務狀態統計:")
            for status, count in sorted(total_by_status.items()):
                print(f"  {status}: {count:,} 筆")
            
            print(f"\n總計: {sum(total_by_vx.values()):,} 筆")
            
            print("\n📅 每日詳細統計:")
            for date in sorted(daily_summary.keys()):
                print(f"\n{date}:")
                for vx_type in ['V1', 'V2', 'V3']:
                    if vx_type in daily_summary[date]:
                        data = daily_summary[date][vx_type]
                        total = sum(data.values())
                        done_rate = (data['DONE'] / total * 100) if total > 0 else 0
                        print(f"  {vx_type}: TODO={data['TODO']}, DOING={data['DOING']}, DONE={data['DONE']}, 完成率={done_rate:.1f}%")
        else:
            print("❌ 未找到符合條件的資料")
        
        # 檢查維度來源
        print("\n🔍 維度來源驗證:")
        dimension_check = client.query("""
        SELECT DISTINCT
            region_source,
            plant_source, 
            factory_source,
            line_source,
            COUNT(*) as record_count
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE region = 'CNE'
          AND plant = 'WJ2'
          AND factory = 'NBU' 
          AND line = 'E5'
          AND task_create_date BETWEEN '2025-12-25' AND '2025-12-31'
          AND is_excluded = 0
        GROUP BY region_source, plant_source, factory_source, line_source
        """)
        
        if dimension_check.result_rows:
            for r_src, p_src, f_src, l_src, count in dimension_check.result_rows:
                print(f"Region:{r_src}, Plant:{p_src}, Factory:{f_src}, Line:{l_src} - {count:,} 筆")
        
        return True
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        client.close()

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ CNE WJ2 NBU E5 任務狀態驗證完成")
    else:
        print(f"\n❌ 驗證失敗")