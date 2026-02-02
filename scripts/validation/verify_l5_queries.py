#!/usr/bin/env python3
"""
執行 L5 指標 SQL 查詢驗證 (含五階維度)
輸出結果為 Markdown 文件
"""

import clickhouse_connect
from datetime import datetime
import os

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

# 輸出檔案路徑
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "l5_query_results.md")

def safe_str(val, default='-'):
    """處理 NULL 值"""
    return str(val) if val is not None else default

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    lines = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 標題
    lines.append("# L5 指標 SQL 查詢驗證結果")
    lines.append("")
    lines.append(f"**執行時間:** {now}")
    lines.append("")
    lines.append("**五階維度:** Region, Vx, Plant, Factory, Line")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 0. 維度欄位檢查
    # ========================================
    lines.append("## 0. FlowableTaskStats 維度欄位檢查")
    lines.append("")
    
    cols_check = client.query("""
        SELECT name, type 
        FROM system.columns 
        WHERE database = 'bronze' AND table = 'common_flowable_task_stats'
        AND name IN ('Plant', 'Factory', 'Line', 'ProductionArea', 'Region', 'DeliveryArea')
        ORDER BY position
    """)
    lines.append("### 可用維度欄位")
    lines.append("")
    lines.append("| 欄位名稱 | 資料類型 |")
    lines.append("|----------|----------|")
    for row in cols_check.result_rows:
        lines.append(f"| {row[0]} | {row[1]} |")
    lines.append("")
    
    # Plant 唯一值
    lines.append("### Plant 唯一值 (Top 10)")
    lines.append("")
    result = client.query("""
        SELECT Plant, count() as cnt 
        FROM bronze.common_flowable_task_stats FINAL 
        WHERE Plant IS NOT NULL AND Plant != ''
        GROUP BY Plant ORDER BY cnt DESC LIMIT 10
    """)
    lines.append("| Plant | 筆數 |")
    lines.append("|-------|------|")
    for row in result.result_rows:
        lines.append(f"| {row[0]} | {row[1]:,} |")
    lines.append("")
    
    # Factory 唯一值
    lines.append("### Factory 唯一值 (Top 10)")
    lines.append("")
    result = client.query("""
        SELECT Factory, count() as cnt 
        FROM bronze.common_flowable_task_stats FINAL 
        WHERE Factory IS NOT NULL AND Factory != ''
        GROUP BY Factory ORDER BY cnt DESC LIMIT 10
    """)
    lines.append("| Factory | 筆數 |")
    lines.append("|---------|------|")
    for row in result.result_rows:
        lines.append(f"| {row[0]} | {row[1]:,} |")
    lines.append("")
    
    # Line 唯一值
    lines.append("### Line 唯一值 (Top 10)")
    lines.append("")
    result = client.query("""
        SELECT Line, count() as cnt 
        FROM bronze.common_flowable_task_stats FINAL 
        WHERE Line IS NOT NULL AND Line != ''
        GROUP BY Line ORDER BY cnt DESC LIMIT 10
    """)
    lines.append("| Line | 筆數 |")
    lines.append("|------|------|")
    for row in result.result_rows:
        lines.append(f"| {row[0]} | {row[1]:,} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 查詢 1：基礎 L5 任務彙總 (含五階維度)
    # ========================================
    lines.append("## 查詢 1：基礎 L5 任務彙總 - 含五階維度 (單日 2025-12-25)")
    lines.append("")
    lines.append("**篩選條件:** Plant=WJ2, Factory=NBU, Line=E5, Date=2025-12-25")
    lines.append("")
    
    query1 = """
    SELECT 
        'CNE' AS region,
        CASE 
            WHEN MoNumber LIKE '315%' THEN 'V1'
            WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                 OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
            WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
            ELSE 'Other'
        END AS vx_type,
        Plant, Factory, Line,
        count() AS total_task,
        countIf(upper(TaskStatus) = 'TODO') AS todo_count,
        countIf(upper(TaskStatus) = 'DOING') AS doing_count,
        countIf(upper(TaskStatus) = 'DONE') AS done_count,
        round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate,
        round(countIf(upper(TaskStatus) IN ('DOING', 'DONE')) * 100.0 / count(), 2) AS execution_rate
    FROM bronze.common_flowable_task_stats FINAL
    WHERE 
        Plant = 'WJ2' AND Factory = 'NBU' AND Line = 'E5'
        AND (toDate(TaskCreateTime) = '2025-12-25'
             OR toDate(TaskClaimTime) = '2025-12-25'
             OR toDate(TaskEndTime) = '2025-12-25')
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
    GROUP BY region, vx_type, Plant, Factory, Line
    ORDER BY total_task DESC
    """
    
    result = client.query(query1)
    lines.append("| Region | Vx | Plant | Factory | Line | Total | TODO | DOING | DONE | 完成率 | 執行率 |")
    lines.append("|--------|-----|-------|---------|------|------:|-----:|------:|-----:|-------:|-------:|")
    for row in result.result_rows:
        lines.append(f"| {safe_str(row[0])} | {safe_str(row[1])} | {safe_str(row[2])} | {safe_str(row[3])} | {safe_str(row[4])} | {row[5]:,} | {row[6]:,} | {row[7]:,} | {row[8]:,} | {row[9]:.2f}% | {row[10]:.2f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 查詢 2：跨維度彙總
    # ========================================
    lines.append("## 查詢 2：跨維度彙總 (不限定 Line，只看 WJ2 NBU)")
    lines.append("")
    lines.append("**篩選條件:** Plant=WJ2, Factory=NBU, Date=2025-12-25")
    lines.append("")
    
    query2 = """
    SELECT 
        'CNE' AS region,
        CASE 
            WHEN MoNumber LIKE '315%' THEN 'V1'
            WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                 OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
            WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
            ELSE 'Other'
        END AS vx_type,
        Plant, Factory, Line,
        count() AS total_task,
        countIf(upper(TaskStatus) = 'TODO') AS todo,
        countIf(upper(TaskStatus) = 'DOING') AS doing,
        countIf(upper(TaskStatus) = 'DONE') AS done,
        round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate
    FROM bronze.common_flowable_task_stats FINAL
    WHERE 
        Plant = 'WJ2' AND Factory = 'NBU'
        AND (toDate(TaskCreateTime) = '2025-12-25'
             OR toDate(TaskClaimTime) = '2025-12-25'
             OR toDate(TaskEndTime) = '2025-12-25')
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
    GROUP BY region, vx_type, Plant, Factory, Line
    ORDER BY Line, vx_type
    """
    
    result = client.query(query2)
    lines.append("| Region | Vx | Plant | Factory | Line | Total | TODO | DOING | DONE | 完成率 |")
    lines.append("|--------|-----|-------|---------|------|------:|-----:|------:|-----:|-------:|")
    for row in result.result_rows:
        lines.append(f"| {safe_str(row[0])} | {safe_str(row[1])} | {safe_str(row[2])} | {safe_str(row[3])} | {safe_str(row[4])} | {row[5]:,} | {row[6]:,} | {row[7]:,} | {row[8]:,} | {row[9]:.2f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 查詢 3：按 Plant 層級彙總
    # ========================================
    lines.append("## 查詢 3：按 Plant 層級彙總 (2025-12-25)")
    lines.append("")
    lines.append("**篩選條件:** Date=2025-12-25 (不限 Plant)")
    lines.append("")
    
    query3 = """
    SELECT 
        'CNE' AS region,
        CASE 
            WHEN MoNumber LIKE '315%' THEN 'V1'
            WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                 OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
            WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
            ELSE 'Other'
        END AS vx_type,
        Plant,
        count() AS total_task,
        countIf(upper(TaskStatus) = 'TODO') AS todo,
        countIf(upper(TaskStatus) = 'DOING') AS doing,
        countIf(upper(TaskStatus) = 'DONE') AS done,
        round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate
    FROM bronze.common_flowable_task_stats FINAL
    WHERE 
        (toDate(TaskCreateTime) = '2025-12-25'
         OR toDate(TaskClaimTime) = '2025-12-25'
         OR toDate(TaskEndTime) = '2025-12-25')
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
    GROUP BY region, vx_type, Plant
    ORDER BY Plant, vx_type
    """
    
    result = client.query(query3)
    lines.append("| Region | Vx | Plant | Total | TODO | DOING | DONE | 完成率 |")
    lines.append("|--------|-----|-------|------:|-----:|------:|-----:|-------:|")
    for row in result.result_rows:
        lines.append(f"| {safe_str(row[0])} | {safe_str(row[1])} | {safe_str(row[2])} | {row[3]:,} | {row[4]:,} | {row[5]:,} | {row[6]:,} | {row[7]:.2f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 查詢 4：按 Factory 層級彙總
    # ========================================
    lines.append("## 查詢 4：按 Factory 層級彙總 (WJ2, 2025-12-25)")
    lines.append("")
    lines.append("**篩選條件:** Plant=WJ2, Date=2025-12-25")
    lines.append("")
    
    query4 = """
    SELECT 
        'CNE' AS region,
        CASE 
            WHEN MoNumber LIKE '315%' THEN 'V1'
            WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                 OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
            WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
            ELSE 'Other'
        END AS vx_type,
        Plant, Factory,
        count() AS total_task,
        countIf(upper(TaskStatus) = 'TODO') AS todo,
        countIf(upper(TaskStatus) = 'DOING') AS doing,
        countIf(upper(TaskStatus) = 'DONE') AS done,
        round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate
    FROM bronze.common_flowable_task_stats FINAL
    WHERE 
        Plant = 'WJ2'
        AND (toDate(TaskCreateTime) = '2025-12-25'
             OR toDate(TaskClaimTime) = '2025-12-25'
             OR toDate(TaskEndTime) = '2025-12-25')
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
    GROUP BY region, vx_type, Plant, Factory
    ORDER BY Factory, vx_type
    """
    
    result = client.query(query4)
    lines.append("| Region | Vx | Plant | Factory | Total | TODO | DOING | DONE | 完成率 |")
    lines.append("|--------|-----|-------|---------|------:|-----:|------:|-----:|-------:|")
    for row in result.result_rows:
        lines.append(f"| {safe_str(row[0])} | {safe_str(row[1])} | {safe_str(row[2])} | {safe_str(row[3])} | {row[4]:,} | {row[5]:,} | {row[6]:,} | {row[7]:,} | {row[8]:.2f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 查詢 5：任務明細樣本
    # ========================================
    lines.append("## 查詢 5：完整五階維度任務明細 (樣本 20 筆)")
    lines.append("")
    lines.append("**篩選條件:** Plant=WJ2, Factory=NBU, Line=E5, Date=2025-12-25")
    lines.append("")
    
    query5 = """
    SELECT 
        'CNE' AS region,
        CASE 
            WHEN MoNumber LIKE '315%' THEN 'V1'
            WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                 OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
            WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
            ELSE 'Other'
        END AS vx_type,
        Plant, Factory, Line,
        TaskDefinitionKey,
        TaskStatus,
        MoNumber,
        toDate(TaskCreateTime) AS create_date
    FROM bronze.common_flowable_task_stats FINAL
    WHERE 
        Plant = 'WJ2' AND Factory = 'NBU' AND Line = 'E5'
        AND (toDate(TaskCreateTime) = '2025-12-25'
             OR toDate(TaskClaimTime) = '2025-12-25'
             OR toDate(TaskEndTime) = '2025-12-25')
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    ORDER BY create_date DESC
    LIMIT 20
    """
    
    result = client.query(query5)
    lines.append("| Region | Vx | Plant | Factory | Line | TaskDefinitionKey | Status | MoNumber | Date |")
    lines.append("|--------|-----|-------|---------|------|-------------------|--------|----------|------|")
    for row in result.result_rows:
        mo = safe_str(row[7])[:12] if row[7] else '-'
        lines.append(f"| {safe_str(row[0])} | {safe_str(row[1])} | {safe_str(row[2])} | {safe_str(row[3])} | {safe_str(row[4])} | {safe_str(row[5])} | {safe_str(row[6])} | {mo} | {row[8]} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 查詢 6：Region 欄位說明
    # ========================================
    lines.append("## 查詢 6：Region 欄位來源確認")
    lines.append("")
    lines.append("> [!WARNING]")
    lines.append("> FlowableTaskStats 表沒有 Region 欄位！")
    lines.append("")
    lines.append("### 五階維度對應表")
    lines.append("")
    lines.append("| 五階維度 | FlowableTaskStats 欄位 | 狀態 |")
    lines.append("|----------|------------------------|------|")
    lines.append("| Region | (無) | ❌ 需從 MDM 補齊 |")
    lines.append("| Vx | TaskDefinitionKey (推導) | ✅ 可用 |")
    lines.append("| Plant | Plant | ✅ 可用 |")
    lines.append("| Factory | Factory | ✅ 可用 |")
    lines.append("| Line | Line | ✅ 可用 |")
    lines.append("")
    lines.append("### Region 補齊方式")
    lines.append("")
    lines.append("1. 從 MDM 主檔 (`silver.dim_mfg_five_level`) 透過 Plant 串接取得 Region")
    lines.append("2. 或直接使用硬編碼 (如 WJ2 → CNE)")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 查詢 7：月份彙總
    # ========================================
    lines.append("## 查詢 7：月份彙總 (含五階維度, 2025-12 ~ 2026-01)")
    lines.append("")
    lines.append("**篩選條件:** Plant=WJ2, Factory=NBU, Line=E5")
    lines.append("")
    
    query7 = """
    SELECT 
        'CNE' AS region,
        CASE 
            WHEN MoNumber LIKE '315%' THEN 'V1'
            WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                 OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
            WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
            ELSE 'Other'
        END AS vx_type,
        Plant, Factory, Line,
        toYYYYMM(coalesce(TaskEndTime, TaskClaimTime, TaskCreateTime)) AS year_month,
        count() AS total_task,
        countIf(upper(TaskStatus) = 'TODO') AS todo,
        countIf(upper(TaskStatus) = 'DOING') AS doing,
        countIf(upper(TaskStatus) = 'DONE') AS done,
        round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate
    FROM bronze.common_flowable_task_stats FINAL
    WHERE 
        Plant = 'WJ2' AND Factory = 'NBU' AND Line = 'E5'
        AND TaskCreateTime >= '2025-12-01' AND TaskCreateTime < '2026-02-01'
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
    GROUP BY region, vx_type, Plant, Factory, Line, year_month
    ORDER BY year_month, vx_type
    """
    
    result = client.query(query7)
    lines.append("| Region | Vx | Plant | Factory | Line | Month | Total | TODO | DOING | DONE | 完成率 |")
    lines.append("|--------|-----|-------|---------|------|-------|------:|-----:|------:|-----:|-------:|")
    for row in result.result_rows:
        lines.append(f"| {safe_str(row[0])} | {safe_str(row[1])} | {safe_str(row[2])} | {safe_str(row[3])} | {safe_str(row[4])} | {row[5]} | {row[6]:,} | {row[7]:,} | {row[8]:,} | {row[9]:,} | {row[10]:.2f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 查詢 8：Gold 層最終驗證 (rmv_l5_task_completion)
    # ========================================
    lines.append("## 查詢 8：Gold 層最終驗證 (自動刷新 View)")
    lines.append("")
    lines.append("**篩選條件:** snapshot_date=2025-12-25, Plant=WJ2, Factory=NBU, Line=E5")
    lines.append("")
    
    query8 = """
    SELECT 
        snapshot_date,
        vx_type,
        region, plant, factory, line,
        total_task,
        todo_count,
        doing_count,
        done_count,
        completion_rate
    FROM gold.rmv_l5_task_completion FINAL
    WHERE 
        snapshot_date = '2025-12-25'
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    ORDER BY vx_type
    """
    
    result = client.query(query8)
    lines.append("| Date | Vx | Region | Plant | Factory | Line | Total | TODO | DOING | DONE | 完成率 |")
    lines.append("|------|-----|--------|-------|---------|------|------:|-----:|------:|-----:|-------:|")
    for row in result.result_rows:
        lines.append(f"| {row[0]} | {safe_str(row[1])} | {safe_str(row[2])} | {safe_str(row[3])} | {safe_str(row[4])} | {safe_str(row[5])} | {row[6]:,} | {row[7]:,} | {row[8]:,} | {row[9]:,} | {row[10]}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ========================================
    # 總結
    # ========================================
    lines.append("## ✅ 查詢驗證結論")
    lines.append("")
    lines.append("### 五階維度對應總結")
    lines.append("")
    lines.append("- ✅ **可從 FlowableTaskStats 直接取得:** Vx (推導), Plant, Factory, Line")
    lines.append("- ❌ **需從其他來源補齊:** Region (透過 MDM 主檔或硬編碼)")
    lines.append("")
    lines.append("### 建議")
    lines.append("")
    lines.append("1. 若需完整五階維度，應 JOIN `silver.dim_mfg_five_level` 取得 Region")
    lines.append("2. 或建立 Plant → Region 的映射表")
    lines.append("")
    
    # 寫入檔案
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ 結果已輸出至: {OUTPUT_FILE}")
    
    client.close()

if __name__ == "__main__":
    main()
