import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\n模擬 QAS Logic (Join Variables) on ClickHouse Bronze Tables:")
    print("目標: 證明若 QAS 使用正確底表 (_0108)，也能算出相同結果。")
    print("篩選: 2025-12-25, WJ2, NBU, E5 (依據 User 提供之 SQL 範例)") # 注意 User SQL 是 E5，我們先跑 E5
    
    # ClickHouse SQL 模擬 T-SQL Logic
    # 使用多個 LEFT JOIN 從 VARINST 提取變數
    # 注意: 會比較慢，因為 Bronze 沒有優化，但應可執行
    
    query = """
    SELECT
        count() as TotalCount,
        countIf(TaskStatus = 'DONE') as DoneCount
    FROM (
        SELECT
            hti.ID_ as TaskID,
            hti.START_TIME_ as StartTime,
            
            -- 模擬變數提取
            COALESCE(var_plant.TEXT_, '') as Plant,
            COALESCE(var_factory.TEXT_, '') as Factory,
            COALESCE(var_lineName.TEXT_, '') as Line,
            
            CASE
                WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                ELSE 'TODO'
            END as TaskStatus
            
        FROM bronze.bpm_act_hi_taskinst hti
        
        -- Join ProcInst (Optional for filtering, but variables are linked to ProcInstId)
        -- LEFT JOIN bronze.bpm_act_hi_procinst hi ON hti.PROC_INST_ID_ = hi.ID_
        
        -- Join Variables (Plant)
        LEFT JOIN (
            SELECT PROC_INST_ID_, TEXT_ FROM bronze.bpm_act_hi_varinst WHERE NAME_ = 'plant'
        ) var_plant ON hti.PROC_INST_ID_ = var_plant.PROC_INST_ID_
        
        -- Join Variables (Factory)
        LEFT JOIN (
            SELECT PROC_INST_ID_, TEXT_ FROM bronze.bpm_act_hi_varinst WHERE NAME_ = 'factory'
        ) var_factory ON hti.PROC_INST_ID_ = var_factory.PROC_INST_ID_
        
        -- Join Variables (Line)
        LEFT JOIN (
            SELECT PROC_INST_ID_, TEXT_ FROM bronze.bpm_act_hi_varinst WHERE NAME_ = 'lineName'
        ) var_lineName ON hti.PROC_INST_ID_ = var_lineName.PROC_INST_ID_
        
        WHERE 1=1
        -- 時間篩選 (QAS Logic: Start OR Claim OR End in range)
        AND (
               (toDateTime(hti.START_TIME_) BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59')
            OR (toDateTime(hti.CLAIM_TIME_) BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59')
            OR (toDateTime(hti.END_TIME_)   BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59')
        )
    )
    WHERE Plant = 'WJ2'
      AND Factory = 'NBU'
      AND Line IN ('E4', 'E5') -- 為了保險起見，我們列出 E4 和 E5 的分佈
    GROUP BY Plant, Factory, Line
    """
    
    final_query = """
    SELECT 
        Plant, 
        Factory, 
        Line, 
        count() as Count 
    FROM (
        """ + query.split("FROM (")[1].replace("    )    WHERE", "    ) A WHERE") + """
    
    GROUP BY Plant, Factory, Line
    ORDER BY Line
    """
    
    # 手動重組 Query 以避免 split/replace 錯誤
    final_query = """
    SELECT Plant, Factory, Line, count() as Count FROM (
        SELECT
            hti.ID_ as TaskID,
            COALESCE(var_plant.TEXT_, '') as Plant,
            COALESCE(var_factory.TEXT_, '') as Factory,
            COALESCE(var_lineName.TEXT_, '') as Line
        FROM bronze.bpm_act_hi_taskinst hti
        LEFT JOIN (SELECT PROC_INST_ID_, TEXT_ FROM bronze.bpm_act_hi_varinst WHERE NAME_ = 'plant') var_plant ON hti.PROC_INST_ID_ = var_plant.PROC_INST_ID_
        LEFT JOIN (SELECT PROC_INST_ID_, TEXT_ FROM bronze.bpm_act_hi_varinst WHERE NAME_ = 'factory') var_factory ON hti.PROC_INST_ID_ = var_factory.PROC_INST_ID_
        LEFT JOIN (SELECT PROC_INST_ID_, TEXT_ FROM bronze.bpm_act_hi_varinst WHERE NAME_ = 'lineName') var_lineName ON hti.PROC_INST_ID_ = var_lineName.PROC_INST_ID_
        WHERE (
               (toDateTime(hti.START_TIME_) BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59')
            OR (toDateTime(hti.CLAIM_TIME_) BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59')
            OR (toDateTime(hti.END_TIME_)   BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59')
        )
    )
    WHERE Plant = 'WJ2' AND Factory = 'NBU' AND Line IN ('E4', 'E5')
    GROUP BY Plant, Factory, Line
    ORDER BY Line
    """
    
    try:
        print("執行查詢中 (可能需要幾秒鐘)...")
        result = client.query(final_query)
        print("\n模擬結果 (基於 Bronze Raw Datas):")
        print("| Plant | Factory | Line | Count |")
        print("|-------|---------|------|-------|")
        for row in result.result_rows:
            print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
            
        print("\n解析:")
        print("如果是 > 100 筆，代表 QAS Logic 在正確的 Raw Data 上會跑出結果。")
        print("目前的 QAS 系統查無資料，是因為它指向了錯誤的舊表 (ACT_HI_TASKINST 無後綴)，而非 _0108 表。")
            
    except Exception as e:
        print(f"查詢失敗: {e}")

if __name__ == "__main__":
    main()
