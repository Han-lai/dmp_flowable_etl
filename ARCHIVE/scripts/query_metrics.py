import clickhouse_connect
import sys

client = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

METRICS = {
    '1': ('在途業務事件總數', """
        SELECT count(*) AS CNT FROM silver.V_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NULL
    """),
    '2': ('在途任務總數', """
        SELECT sum(TASK_TODO_CNT + TASK_DOING_CNT) AS CNT FROM silver.V_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NULL
    """),
    '3': ('事件自動完成率', """
        SELECT 
            countIf(TASK_STATUS = 'DONE') AS done_cnt,
            countIf(TASK_STATUS = 'DONE_AUTO') AS auto_cnt,
            round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) AS auto_rate_pct
        FROM silver.V_HI_PROC_TASK_NODE
    """),
    '4': ('TASK_STATUS 分布', """
        SELECT TASK_STATUS, count(*) AS cnt FROM silver.V_HI_PROC_TASK_NODE GROUP BY TASK_STATUS ORDER BY cnt DESC
    """),
    '5': ('在途任務數 - 依廠區', """
        SELECT coalesce(PLANT, 'Unknown') AS PLANT, count(*) AS CNT 
        FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING') 
        GROUP BY PLANT ORDER BY CNT DESC LIMIT 10
    """),
    '6': ('在途任務數 - 依部門', """
        SELECT coalesce(DEPT_NAME, 'Unknown') AS DEPT, count(*) AS CNT 
        FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING') 
        GROUP BY DEPT ORDER BY CNT DESC LIMIT 10
    """),
    '7': ('在途任務數 - 依人員', """
        SELECT coalesce(ASSIGNEE, 'Unassigned') AS ASSIGNEE, count(*) AS CNT 
        FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING') 
        GROUP BY ASSIGNEE ORDER BY CNT DESC LIMIT 10
    """),
    '8': ('平均業務事件總歷時 (秒)', """
        SELECT round(avg(TOTAL_DURATION_SEC), 2) AS AVG_SEC FROM silver.V_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NOT NULL
    """),
    '9': ('平均任務處理時長 (秒)', """
        SELECT round(avg(WORK_DURATION_SEC), 2) AS AVG_SEC FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'
    """),
    '10': ('在途流程健康度快照 (Top 10)', """
        SELECT coalesce(FIRST_PROC_DEF_NAME, 'Unknown') AS PROC_NAME, count(*) AS CNT 
        FROM silver.V_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NULL 
        GROUP BY PROC_NAME ORDER BY CNT DESC LIMIT 10
    """),
    '11': ('依流程的自動完成率 (Top 10)', """
        SELECT PROC_DEF_NAME, countIf(TASK_STATUS = 'DONE') AS done, countIf(TASK_STATUS = 'DONE_AUTO') AS auto,
               round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) AS rate
        FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('DONE', 'DONE_AUTO')
        GROUP BY PROC_DEF_NAME HAVING (done + auto) >= 10 ORDER BY (done + auto) DESC LIMIT 10
    """),
}

def show_menu():
    print("\n=== 指標查詢工具 ===")
    for k, v in METRICS.items():
        print(f"  {k}. {v[0]}")
    print("  0. 執行全部")
    print("  q. 離開")

def run_query(key):
    name, sql = METRICS[key]
    print(f"\n--- {name} ---")
    result = client.query(sql.strip())
    cols = result.column_names
    print(" | ".join(cols))
    print("-" * 50)
    for row in result.result_rows:
        print(" | ".join(str(x) for x in row))

def main():
    if len(sys.argv) > 1:
        key = sys.argv[1]
        if key == '0':
            for k in METRICS:
                run_query(k)
        elif key in METRICS:
            run_query(key)
        return
    
    while True:
        show_menu()
        choice = input("\n選擇指標 (1-11, 0=全部, q=離開): ").strip()
        if choice == 'q':
            break
        elif choice == '0':
            for k in METRICS:
                run_query(k)
        elif choice in METRICS:
            run_query(choice)
        else:
            print("無效選項")

if __name__ == '__main__':
    main()
