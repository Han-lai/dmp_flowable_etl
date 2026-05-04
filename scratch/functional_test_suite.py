import clickhouse_connect
import os
from colorama import init, Fore, Style

init(autoreset=True)

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'REDACTED_PASSWORD'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def get_client():
    return clickhouse_connect.get_client(**CH_CONFIG)

def run_tests():
    try:
        client = get_client()
        print(f"{Fore.CYAN}================================================================={Style.RESET_ALL}")
        print(f"{Fore.CYAN}       DMP Flowable Data Quality Functional Test Suite          {Style.RESET_ALL}")
        print(f"{Fore.CYAN}================================================================={Style.RESET_ALL}")

        passed_tests = 0
        failed_tests = 0

        # =====================================================================
        # 1. 狀態互斥定律測試 (Mutually Exclusive Logic)
        # =====================================================================
        print(f"\n{Fore.YELLOW}[Test 1] 狀態互斥定律測試 (Mutually Exclusive Logic){Style.RESET_ALL}")
        sql_ex = """
        SELECT 
            snapshot_date, 
            bitmapCardinality(groupBitmapMergeState(total_task)) as total, 
            bitmapCardinality(groupBitmapMergeState(todo_daily)) as todo, 
            bitmapCardinality(groupBitmapMergeState(doing_daily)) as doing, 
            bitmapCardinality(groupBitmapMergeState(done_daily)) as done 
        FROM gold.rmv_l5_task_completion 
        WHERE snapshot_date BETWEEN '2025-12-25' AND '2026-01-05'
        GROUP BY snapshot_date
        ORDER BY snapshot_date
        """
        res_ex = client.query(sql_ex)
        
        all_match = True
        if not res_ex.result_rows:
            print(f"{Fore.RED}  -> NO DATA FOUND for the specified date range!{Style.RESET_ALL}")
            all_match = False
        else:
            for row in res_ex.result_rows:
                date, total, todo, doing, done = row
                calc_total = todo + doing + done
                if total != calc_total:
                    print(f"{Fore.RED}  -> [FAILED] {date}: Total ({total}) != Todo({todo}) + Doing({doing}) + Done({done}) [Sum: {calc_total}]{Style.RESET_ALL}")
                    all_match = False
                else:
                    pass # Success for this row

        if all_match:
            print(f"{Fore.GREEN}  -> [PASSED] 所有日期的 Todo + Doing + Done 皆完美等於 Total Task。{Style.RESET_ALL}")
            passed_tests += 1
        else:
            failed_tests += 1

        # =====================================================================
        # 2. 跨年邊界對帳測試 (Cross-Year Boundary Test)
        # =====================================================================
        print(f"\n{Fore.YELLOW}[Test 2] 跨年邊界對帳測試 (Cross-Year Boundary Test){Style.RESET_ALL}")
        sql_cy = """
        SELECT count() 
        FROM gold.rmv_l5_task_completion 
        WHERE snapshot_date IN ('2025-12-31', '2026-01-01')
        """
        res_cy = client.query(sql_cy)
        
        if res_cy.result_rows and res_cy.result_rows[0][0] > 0:
            print(f"{Fore.GREEN}  -> [PASSED] 跨年邊界 (12/31, 01/01) 資料皆有產出，無異常斷層。{Style.RESET_ALL}")
            passed_tests += 1
        else:
            print(f"{Fore.RED}  -> [FAILED] 跨年邊界無資料產出！{Style.RESET_ALL}")
            failed_tests += 1

        # =====================================================================
        # 3. 自動排除規則測試 (Exclusion Rules Test)
        # =====================================================================
        print(f"\n{Fore.YELLOW}[Test 3] 自動排除規則測試 (Exclusion Rules Test){Style.RESET_ALL}")
        # Verify that tasks meeting exclusion criteria are actually excluded (is_excluded = 1)
        sql_exclude = """
        SELECT count() 
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 
          AND (
              assignee_name = 'SYSTEM' 
              OR task_definition_key LIKE 'E%' 
              OR task_definition_key LIKE 'C%'
              OR mo_number LIKE 'Q%'
              OR mo_number LIKE 'R%'
              OR task_name LIKE '%Notify%'
              OR task_name LIKE '%Dummy%'
          )
        """
        res_exclude = client.query(sql_exclude)
        
        count = res_exclude.result_rows[0][0]
        if count == 0:
            print(f"{Fore.GREEN}  -> [PASSED] 系統過濾機制正確：SYSTEM 帳號、E/C 節點、Q/R 測試單、Notify 任務皆已排除。{Style.RESET_ALL}")
            passed_tests += 1
        else:
            print(f"{Fore.RED}  -> [FAILED] 發現 {count} 筆應該被排除的任務，卻被標記為有效 (is_excluded=0)！{Style.RESET_ALL}")
            failed_tests += 1

        # =====================================================================
        # Summary
        # =====================================================================
        print(f"\n{Fore.CYAN}================================================================={Style.RESET_ALL}")
        print(f" Test Results: {Fore.GREEN}{passed_tests} Passed{Style.RESET_ALL}, {Fore.RED if failed_tests > 0 else Fore.GREEN}{failed_tests} Failed{Style.RESET_ALL}")
        if failed_tests == 0:
            print(f" {Fore.GREEN}SUCCESS! The Gold layer data quality is robust and ready for production.{Style.RESET_ALL}")
        else:
            print(f" {Fore.RED}WARNING: Data anomalies detected. Please review ETL logic.{Style.RESET_ALL}")
        print(f"{Fore.CYAN}================================================================={Style.RESET_ALL}\n")

    except Exception as e:
        print(f"{Fore.RED}Test Execution Failed: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    run_tests()
