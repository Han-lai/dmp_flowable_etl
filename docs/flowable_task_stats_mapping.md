# FlowableTaskStats 與 L5 指標欄位對應文件

**版本：** 1.0  
**建立日期：** 2026-01-30  
**資料來源：** `bronze.common_flowable_task_stats` (來自 `APP_SRV_COMMON.dbo.FlowableTaskStats`)

---

## 📊 概述

本文件說明 `FlowableTaskStats` 表如何對應 `metric_definitions.md` 中定義的 L5 任務指標。

**結論**：FlowableTaskStats 表包含計算 L5 指標所需的**所有核心欄位**，覆蓋率符合要求。

---

## 🎯 L5 任務完成率指標對應

### 篩選條件欄位

| 指標需求 | FlowableTaskStats 欄位 | 資料類型 | 使用方式 |
|---------|----------------------|---------|---------|
| Vx 類型 | `TaskDefinitionKey` | String | `substring(TaskDefinitionKey, 1, 2)` 取得 V1/V2/V3 |
| Plant | `Plant` | String | 直接篩選 `WHERE Plant = 'WJ2'` |
| Factory | `Factory` | String | 直接篩選 `WHERE Factory = 'NBU'` |
| Line | `Line` | String | 直接篩選 `WHERE Line = 'E5'` |

---

### 任務狀態統計欄位

| 指標項目 | FlowableTaskStats 欄位 | 計算邏輯 |
|---------|----------------------|---------|
| **Total Task** | `TaskStatus` + `TaskBypass` | `COUNT(*) WHERE TaskBypass = 'N'` |
| **Todo** | `TaskStatus` | `COUNT(*) WHERE TaskStatus = 'TODO' AND TaskBypass = 'N'` |
| **Doing** | `TaskStatus` | `COUNT(*) WHERE TaskStatus = 'DOING' AND TaskBypass = 'N'` |
| **Done** | `TaskStatus` | `COUNT(*) WHERE TaskStatus = 'DONE' AND TaskBypass = 'N'` |
| **Doing + Done** | `TaskStatus` | `Doing + Done` |
| **完成率 (%)** | 計算欄位 | `Done / Total Task * 100` |
| **執行率 (%)** | 計算欄位 | `(Doing + Done) / Total Task * 100` |

---

### 時間篩選欄位

| 時間類型 | FlowableTaskStats 欄位 | 對應原生表欄位 | 說明 |
|---------|----------------------|---------------|------|
| 任務開始時間 | `TaskCreateTime` | `ACT_HI_TASKINST.START_TIME_` | 任務創建時間 |
| 任務認領時間 | `TaskClaimTime` | `ACT_HI_TASKINST.CLAIM_TIME_` | 可能為空 (自動任務) |
| 任務結束時間 | `TaskEndTime` | `ACT_HI_TASKINST.END_TIME_` | 任務完成時設定 |

**時間篩選邏輯** (符合 metric_definitions.md)：
```sql
WHERE (
    toDate(TaskCreateTime) = '2025-12-25'
    OR toDate(TaskClaimTime) = '2025-12-25'
    OR toDate(TaskEndTime) = '2025-12-25'
)
```

---

## 🔄 Vx 歸屬規則對應

### 基本歸屬規則

| 規則 | FlowableTaskStats 欄位 | 判斷邏輯 |
|-----|----------------------|---------|
| V1 任務 | `TaskDefinitionKey` | `TaskDefinitionKey LIKE 'V1%'` |
| V2 任務 | `TaskDefinitionKey` | `TaskDefinitionKey LIKE 'V2%'` |
| V3 任務 | `TaskDefinitionKey` | `TaskDefinitionKey LIKE 'V3%'` |

### V1 工單號特殊規則 (優先級最高)

| 規則 | FlowableTaskStats 欄位 | 判斷邏輯 | 覆蓋率 |
|-----|----------------------|---------|--------|
| 315% 工單 | `MoNumber` | `MoNumber LIKE '315%'` | 96.23% (V1) |
| 196% 工單 | `MoNumber` | `MoNumber LIKE '196%'` | 96.23% (V1) |
| 199% 工單 | `MoNumber` | `MoNumber LIKE '199%'` | 96.23% (V1) |
| 200% 工單 | `MoNumber` | `MoNumber LIKE '200%'` | 96.23% (V1) |
| 210% 工單 | `MoNumber` | `MoNumber LIKE '210%'` | 96.23% (V1) |
| 212% 工單 | `MoNumber` | `MoNumber LIKE '212%'` | 96.23% (V1) |
| 213% 工單 | `MoNumber` | `MoNumber LIKE '213%'` | 96.23% (V1) |

**完整 Vx 歸屬 SQL 邏輯**：
```sql
CASE 
    -- 工單號規則優先
    WHEN MoNumber LIKE '315%' THEN 'V1'
    WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
         OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
    -- 任務定義鍵規則其次
    WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
    WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
    ELSE substring(TaskDefinitionKey, 1, 2)
END AS vx_type
```

---

## 🏭 NPE 判別規則對應

| 規則 | FlowableTaskStats 欄位 | 判斷邏輯 | 資料量 |
|-----|----------------------|---------|--------|
| V1 NPE | `Factory` | `Factory = 'NPE'` 或 `Factory LIKE '%NPE%'` | 1,972 筆 |
| V1 MFG | `Factory` | `Factory != 'NPE'` (非 NPE) | 其餘 V1 任務 |

---

## 🚫 排除規則對應

| 排除規則 | FlowableTaskStats 欄位 | 判斷邏輯 |
|---------|----------------------|---------|
| 排除 Bypass 任務 | `TaskBypass` | `TaskBypass = 'N' OR TaskBypass IS NULL` |
| 排除 E 開頭任務 | `TaskDefinitionKey` | `TaskDefinitionKey NOT LIKE 'E%'` |
| 排除 C 開頭任務 | `TaskDefinitionKey` | `TaskDefinitionKey NOT LIKE 'C%'` |
| 排除 Q 工單 | `MoNumber` | `MoNumber NOT LIKE 'Q%'` |
| 排除 R 工單 | `MoNumber` | `MoNumber NOT LIKE 'R%'` |

---

## 📈 欄位覆蓋率驗證結果

**驗證日期**：2026-01-30

### MoNumber 覆蓋率

| Vx 類型 | 總筆數 | 有 MoNumber | 覆蓋率 |
|--------|--------|-------------|--------|
| V1 | 264,199 | 254,236 | **96.23%** ✅ |
| V2 | 65,333 | 59,244 | **90.68%** ✅ |
| V3 | 58,919 | 58,919 | **100.00%** ✅ |

### Factory 欄位分布 (Top 10)

| Factory | 筆數 | 備註 |
|---------|------|------|
| MULTI | 248,680 | |
| FAKE | 37,323 | |
| NBU | 14,944 | |
| SV | 11,160 | |
| SMT | 6,967 | |
| **NPE** | **1,961** | **可識別 NPE** |
| FMBG_FAN | 1,189 | |
| FAN2 | 815 | |
| NW | 688 | |
| IPS | 176 | |

---

## 📋 完整欄位清單

| # | 欄位名稱 | 資料類型 | L5 指標用途 |
|---|---------|---------|------------|
| 1 | Id | Decimal(38,0) | 主鍵 |
| 2 | ProcessInstanceId | String | 流程實例識別 |
| 3 | ProcessDefinitionKey | String | 流程定義 |
| 4 | ProcessDefinitionName | String | 流程名稱 |
| 5 | ProcessTeam | String | 流程團隊 |
| 6 | **Plant** | String | **維度篩選** |
| 7 | **Factory** | String | **維度篩選 + NPE 判別** |
| 8 | ProductionArea | String | 生產區域 |
| 9 | **Line** | String | **維度篩選** |
| 10 | ModelName | String | 機型 |
| 11 | DeliveryArea | String | 交貨區域 |
| 12 | ScheduleNumber | String | 排程編號 |
| 13 | **MoNumber** | String | **工單號歸屬規則** |
| 14 | SapPlant | String | SAP 廠區 |
| 15 | SapProductGroup | String | SAP 產品群組 |
| 16 | Pallet | String | 棧板 |
| 17 | TransferNo | String | 移轉編號 |
| 18 | QBlockEventId | String | Q Block 事件 |
| 19 | DefectSn | String | 缺陷序號 |
| 20 | Time_ | String | 時間 |
| 21 | TaskId | String | 任務 ID |
| 22 | **TaskDefinitionKey** | String | **Vx 類型識別** |
| 23 | TaskName | String | 任務名稱 |
| 24 | **TaskStatus** | String | **狀態統計 (TODO/DOING/DONE)** |
| 25 | **TaskBypass** | String | **排除 Bypass 任務** |
| 26 | TaskAssignee | String | 指派人代碼 |
| 27 | TaskAssigneeAccount | String | 指派人帳號 |
| 28 | TaskAssigneeName | String | 指派人姓名 |
| 29 | **TaskCreateTime** | DateTime | **時間篩選** |
| 30 | **TaskClaimTime** | DateTime | **時間篩選** |
| 31 | **TaskEndTime** | DateTime | **時間篩選** |
| 32 | TaskDurationMinutes | Float64 | 任務總時長 |
| 33 | TaskWorkMinutes | Float64 | 任務工作時長 |
| 34 | DeleteReason | String | 刪除原因 |
| 35 | SyncTime | DateTime64(7) | 同步時間 |
| 36 | LastUpdatedTime | DateTime64(7) | 最後更新時間 |
| 37 | TaskCreateDate | Date | 任務建立日期 |
| 38 | TaskClaimDate | Date | 任務認領日期 |
| 39 | TaskEndDate | Date | 任務結束日期 |

---

## ✅ 結論

`FlowableTaskStats` 表**完全符合** `metric_definitions.md` 中 L5 任務指標的計算需求：

1. ✅ **任務狀態統計**：TaskStatus 欄位可區分 TODO/DOING/DONE
2. ✅ **Vx 類型識別**：TaskDefinitionKey 前兩碼可識別 V1/V2/V3
3. ✅ **工單號歸屬規則**：MoNumber 覆蓋率 90%+ 足以支持 315%/196% 等規則
4. ✅ **NPE 判別**：Factory 欄位可區分 NPE vs MFG
5. ✅ **排除規則**：TaskBypass、TaskDefinitionKey、MoNumber 可實現所有排除邏輯
6. ✅ **時間篩選**：TaskCreateTime/ClaimTime/EndTime 完整支持 OR 條件篩選
7. ✅ **維度篩選**：Plant/Factory/Line 欄位直接可用

---

## 📝 L5 指標 SQL 查詢範例

以下 SQL 查詢可直接從 `bronze.common_flowable_task_stats` 生成 L5 任務指標。

### 參數說明

```sql
-- 查詢參數
SET @plant = 'WJ2';
SET @factory = 'NBU';
SET @line = 'E5';
SET @target_date = '2025-12-25';
SET @month_start = '2025-12-01';
SET @month_end = '2025-12-31';
```

---

### 查詢 1：基礎 L5 任務彙總 (單日)

按 Vx 類型統計 Total Task、TODO、DOING、DONE 及完成率。

```sql
-- ClickHouse 版本
SELECT 
    -- Vx 類型判斷 (工單號規則優先)
    CASE 
        WHEN MoNumber LIKE '315%' THEN 'V1'
        WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
             OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
        WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        ELSE 'Other'
    END AS vx_type,
    
    -- 任務數統計
    count() AS total_task,
    countIf(upper(TaskStatus) = 'TODO') AS todo_count,
    countIf(upper(TaskStatus) = 'DOING') AS doing_count,
    countIf(upper(TaskStatus) = 'DONE') AS done_count,
    
    -- 完成率與執行率
    round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate,
    round(countIf(upper(TaskStatus) IN ('DOING', 'DONE')) * 100.0 / count(), 2) AS execution_rate

FROM bronze.common_flowable_task_stats FINAL
WHERE 
    -- 維度篩選
    Plant = 'WJ2'
    AND Factory = 'NBU'
    AND Line = 'E5'
    -- 時間篩選 (OR 條件)
    AND (
        toDate(TaskCreateTime) = '2025-12-25'
        OR toDate(TaskClaimTime) = '2025-12-25'
        OR toDate(TaskEndTime) = '2025-12-25'
    )
    -- 排除規則
    AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    AND TaskDefinitionKey NOT LIKE 'E%'
    AND TaskDefinitionKey NOT LIKE 'C%'
    AND (MoNumber NOT LIKE 'Q%' OR MoNumber IS NULL)
    AND (MoNumber NOT LIKE 'R%' OR MoNumber IS NULL)
    
GROUP BY vx_type
ORDER BY total_task DESC;
```

---

### 查詢 2：L5 任務狀態明細表 (符合 metric_definitions.md 格式)

生成 6 行指標行：Total Task、Todo、Doing、Done、Doing+Done、Todo+Doing (Acc)。

```sql
-- ClickHouse 版本
WITH base_data AS (
    SELECT 
        CASE 
            WHEN MoNumber LIKE '315%' THEN 'V1'
            WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                 OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
            WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
            ELSE 'Other'
        END AS vx_type,
        upper(TaskStatus) AS status
    FROM bronze.common_flowable_task_stats FINAL
    WHERE 
        Plant = 'WJ2' AND Factory = 'NBU' AND Line = 'E5'
        AND (toDate(TaskCreateTime) = '2025-12-25'
             OR toDate(TaskClaimTime) = '2025-12-25'
             OR toDate(TaskEndTime) = '2025-12-25')
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
),
summary AS (
    SELECT 
        vx_type,
        count() AS total_task,
        countIf(status = 'TODO') AS todo,
        countIf(status = 'DOING') AS doing,
        countIf(status = 'DONE') AS done
    FROM base_data
    GROUP BY vx_type
)
SELECT 
    vx_type,
    'Total Task' AS item,
    total_task AS task_qty,
    '-' AS pct
FROM summary

UNION ALL

SELECT 
    vx_type,
    'Todo' AS item,
    todo AS task_qty,
    concat(toString(round(todo * 100.0 / total_task, 1)), '%') AS pct
FROM summary

UNION ALL

SELECT 
    vx_type,
    'Doing' AS item,
    doing AS task_qty,
    concat(toString(round(doing * 100.0 / total_task, 1)), '%') AS pct
FROM summary

UNION ALL

SELECT 
    vx_type,
    'Done' AS item,
    done AS task_qty,
    concat(toString(round(done * 100.0 / total_task, 1)), '%') AS pct
FROM summary

UNION ALL

SELECT 
    vx_type,
    'Doing + Done' AS item,
    doing + done AS task_qty,
    concat(toString(round((doing + done) * 100.0 / total_task, 1)), '%') AS pct
FROM summary

UNION ALL

SELECT 
    vx_type,
    'Todo + Doing (Acc)' AS item,
    todo + doing AS task_qty,
    concat(toString(round((todo + doing) * 100.0 / total_task, 1)), '%') AS pct
FROM summary

ORDER BY vx_type, 
    CASE item 
        WHEN 'Total Task' THEN 1
        WHEN 'Todo' THEN 2
        WHEN 'Doing' THEN 3
        WHEN 'Done' THEN 4
        WHEN 'Doing + Done' THEN 5
        WHEN 'Todo + Doing (Acc)' THEN 6
    END;
```

---

### 查詢 3：V1 NPE vs V1 MFG 細分

根據 Factory 欄位區分 V1 NPE 和 V1 MFG。

```sql
-- ClickHouse 版本
SELECT 
    -- V1 細分
    CASE 
        WHEN Factory = 'NPE' OR Factory LIKE '%NPE%' THEN 'V1_NPE'
        ELSE 'V1_MFG'
    END AS v1_category,
    
    count() AS total_task,
    countIf(upper(TaskStatus) = 'TODO') AS todo,
    countIf(upper(TaskStatus) = 'DOING') AS doing,
    countIf(upper(TaskStatus) = 'DONE') AS done,
    round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate

FROM bronze.common_flowable_task_stats FINAL
WHERE 
    Plant = 'WJ2'
    AND (
        toDate(TaskCreateTime) = '2025-12-25'
        OR toDate(TaskClaimTime) = '2025-12-25'
        OR toDate(TaskEndTime) = '2025-12-25'
    )
    AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    AND TaskDefinitionKey NOT LIKE 'E%'
    AND TaskDefinitionKey NOT LIKE 'C%'
    -- 只看 V1 任務 (含工單號特殊規則)
    AND (
        MoNumber LIKE '315%' 
        OR MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
        OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%'
        OR TaskDefinitionKey LIKE 'V1%'
    )
    
GROUP BY v1_category
ORDER BY v1_category;
```

---

### 查詢 4：週次 (ISO Week) 彙總

按 ISO 週次統計 L5 任務。

```sql
-- ClickHouse 版本
SELECT 
    toISOWeek(coalesce(TaskEndTime, TaskClaimTime, TaskCreateTime)) AS iso_week,
    toISOYear(coalesce(TaskEndTime, TaskClaimTime, TaskCreateTime)) AS iso_year,
    
    CASE 
        WHEN MoNumber LIKE '315%' THEN 'V1'
        WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
             OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
        WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        ELSE 'Other'
    END AS vx_type,
    
    count() AS total_task,
    countIf(upper(TaskStatus) = 'TODO') AS todo,
    countIf(upper(TaskStatus) = 'DOING') AS doing,
    countIf(upper(TaskStatus) = 'DONE') AS done,
    round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate

FROM bronze.common_flowable_task_stats FINAL
WHERE 
    Plant = 'WJ2' AND Factory = 'NBU' AND Line = 'E5'
    AND TaskCreateTime >= '2025-12-01'
    AND TaskCreateTime < '2026-01-01'
    AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    AND TaskDefinitionKey NOT LIKE 'E%'
    AND TaskDefinitionKey NOT LIKE 'C%'
    
GROUP BY iso_year, iso_week, vx_type
ORDER BY iso_year, iso_week, vx_type;
```

---

### 查詢 5：每日 (Dn-1 ~ Dn-7) 趨勢

計算最近 7 天的每日任務數。

```sql
-- ClickHouse 版本
SELECT 
    toDate(coalesce(TaskEndTime, TaskClaimTime, TaskCreateTime)) AS task_date,
    
    CASE 
        WHEN MoNumber LIKE '315%' THEN 'V1'
        WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
             OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
        WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        ELSE 'Other'
    END AS vx_type,
    
    count() AS total_task,
    countIf(upper(TaskStatus) = 'TODO') AS todo,
    countIf(upper(TaskStatus) = 'DOING') AS doing,
    countIf(upper(TaskStatus) = 'DONE') AS done,
    round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate

FROM bronze.common_flowable_task_stats FINAL
WHERE 
    Plant = 'WJ2' AND Factory = 'NBU' AND Line = 'E5'
    -- 最近 7 天
    AND (
        toDate(TaskCreateTime) >= today() - 7
        OR toDate(TaskClaimTime) >= today() - 7
        OR toDate(TaskEndTime) >= today() - 7
    )
    AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    AND TaskDefinitionKey NOT LIKE 'E%'
    AND TaskDefinitionKey NOT LIKE 'C%'
    
GROUP BY task_date, vx_type
ORDER BY task_date DESC, vx_type;
```

---

### 查詢 6：月份彙總 (Total)

計算整月的任務彙總。

```sql
-- ClickHouse 版本
SELECT 
    toYYYYMM(coalesce(TaskEndTime, TaskClaimTime, TaskCreateTime)) AS year_month,
    
    CASE 
        WHEN MoNumber LIKE '315%' THEN 'V1'
        WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
             OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
        WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        ELSE 'Other'
    END AS vx_type,
    
    count() AS total_task,
    countIf(upper(TaskStatus) = 'TODO') AS todo,
    countIf(upper(TaskStatus) = 'DOING') AS doing,
    countIf(upper(TaskStatus) = 'DONE') AS done,
    round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate,
    round(countIf(upper(TaskStatus) IN ('DOING', 'DONE')) * 100.0 / count(), 2) AS execution_rate

FROM bronze.common_flowable_task_stats FINAL
WHERE 
    Plant = 'WJ2' AND Factory = 'NBU' AND Line = 'E5'
    AND TaskCreateTime >= '2025-12-01'
    AND TaskCreateTime < '2026-01-01'
    AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    AND TaskDefinitionKey NOT LIKE 'E%'
    AND TaskDefinitionKey NOT LIKE 'C%'
    
GROUP BY year_month, vx_type
ORDER BY year_month, vx_type;
```

---

### 查詢 7：完整 L5 Dashboard 報表 (多時間粒度)

生成包含 Total、Month、Week、Daily 的完整報表結構。

```sql
-- ClickHouse 版本 - 完整報表範例
WITH params AS (
    SELECT 
        'WJ2' AS p_plant,
        'NBU' AS p_factory,
        'E5' AS p_line,
        toDate('2025-12-25') AS p_date
),
base_data AS (
    SELECT 
        t.*,
        CASE 
            WHEN MoNumber LIKE '315%' THEN 'V1'
            WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                 OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
            WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
            WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
            ELSE 'Other'
        END AS vx_type,
        coalesce(toDate(TaskEndTime), toDate(TaskClaimTime), toDate(TaskCreateTime)) AS task_date,
        toISOWeek(coalesce(TaskEndTime, TaskClaimTime, TaskCreateTime)) AS iso_week
    FROM bronze.common_flowable_task_stats t FINAL
    CROSS JOIN params p
    WHERE 
        t.Plant = p.p_plant AND t.Factory = p.p_factory AND t.Line = p.p_line
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
)
SELECT 
    vx_type,
    task_date,
    iso_week,
    count() AS total_task,
    countIf(upper(TaskStatus) = 'TODO') AS todo,
    countIf(upper(TaskStatus) = 'DOING') AS doing,
    countIf(upper(TaskStatus) = 'DONE') AS done,
    round(countIf(upper(TaskStatus) = 'DONE') * 100.0 / count(), 2) AS completion_rate
FROM base_data
WHERE task_date >= today() - 30
GROUP BY vx_type, task_date, iso_week
ORDER BY task_date DESC, vx_type;
```

---

## 🔧 使用注意事項

### 1. FINAL 關鍵字
FlowableTaskStats 使用 `ReplacingMergeTree` 引擎，查詢時需加上 `FINAL` 確保資料去重。

### 2. 時間篩選邏輯
務必使用 OR 條件連接三個時間欄位，確保任務在任一時間點落入範圍即被包含：
```sql
WHERE (
    toDate(TaskCreateTime) = 'YYYY-MM-DD'
    OR toDate(TaskClaimTime) = 'YYYY-MM-DD'
    OR toDate(TaskEndTime) = 'YYYY-MM-DD'
)
```

### 3. Vx 歸屬優先級
工單號規則(315%/196%等) > TaskDefinitionKey 規則(V1%/V2%/V3%)

### 4. 效能優化
- 優先篩選 Plant/Factory/Line 維度
- 使用日期範圍而非 toDate() 函數進行時間篩選可提升效能
- 對於大範圍查詢，考慮使用物化視圖預計算
