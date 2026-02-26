# 待修復：Silver 層 Vx (V1/V3) 歸屬邏輯重構計畫

## 核心問題 (Bug Description)
目前 `04_silver_fact_tasks.sql` 的 `vx_type` 判斷邏輯存在兩大缺陷，導致 ClickHouse 聚合的資料與業務報表 (Superset) 嚴重不符：

1. **判斷順序錯誤**：`TASK_DEF_KEY_` 被放置在最優先順序，導致所有帶有特定前綴 (196/199/315等) 的 V3 任務被提前誤判為 V3 結案，後續的工單特權邏輯無法執行。這造成如 DG3, WJ2/NPE3 等廠區的 V1 資料大幅短缺。
2. **缺乏廠區 (Factory/Plant) 限定**：業務規則中，工單強迫轉 V1 的特權是帶有「地域性」的（例如 NPE 廠區）。若直接將所有 `315` 工單全轉 V1，會將原本正確歸屬於 V3 的 WJ2/NBU/E5 線體數據誤殺為 V1。

## 解決方案 (Proposed Solution)
將 `vx_type` 邏輯重構為「廠區與工單號聯合判斷」，並將特權名單置於 `TASK_DEF_KEY_` 之上。

```sql
CASE 
    -- 【規則 1：DG3 廠區的特權工單 -> 強制轉 V1】
    -- 涵蓋 DG3/SMT/ST02 的業務邏輯
    WHEN COALESCE(NULLIF(mv_varinst_pivoted.varinst_plant, ''), mdm.plant_code, '') = 'DG3' 
         AND substring(COALESCE(mv_varinst_pivoted.varinst_moNumber, ''), 1, 3) IN ('196','199','200','210','212','213','315') 
    THEN 'V1'
    
    -- 【規則 2：NPE 廠區的特權工單 -> 強制轉 V1】
    -- 涵蓋包含「NPE」字眼廠區的業務邏輯 (例如 WJ2/NPE/NPE3)
    WHEN (
           COALESCE(NULLIF(mv_varinst_pivoted.varinst_factory, ''), mdm.factory_code, '') LIKE '%NPE%' 
           OR COALESCE(NULLIF(mv_varinst_pivoted.varinst_plant, ''), mdm.plant_code, '') LIKE '%NPE%'
         )
         AND substring(COALESCE(mv_varinst_pivoted.varinst_moNumber, ''), 1, 3) IN ('196','199','200','210','212','213','315') 
    THEN 'V1'
    
    -- 【規則 3：不滿足特規的其他廠區 -> 回歸 TASK_DEF_KEY_】
    -- 例如 WJ2/NBU/E5 擁有 315 工單，但因廠區不是 DG3 也無 NPE，會落入此判斷，被正確識別為 V3
    WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
    
    -- 兜底
    ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
END AS vx_type
```

## 注意事項 (Notes)
1. 根據使用者的要求，**不**將 `369` 工單加入特權轉換前綴清單中（儘管 NPE3 資料庫中有大量 369 的 V3 任務）。
2. 在尚未授權前，暫不可將此邏輯部署至正式 `04_silver_fact_tasks.sql` 中。這份指南僅作為已驗證之知識備存。
