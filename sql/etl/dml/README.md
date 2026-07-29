# DML 檔案說明

> 最後校準: 2026-07-03（對照 `scripts/etl/config/pipeline_config.yaml` 驗證）
> 執行順序與對應關係的唯一真相是 `pipeline_config.yaml`，本檔僅為導讀。

## 執行順序（execute_etl.py 依 pipeline_config.yaml 逐時間視窗執行）

| # | phase_id | 檔案 | 目標表 | 說明 |
|---|----------|------|--------|------|
| 1 | silver_varinst_pivoted | `backfill_pivot.sql` | `silver.mv_varinst_pivoted` | EAV 變數轉置寬表（varinst 回溯 365 天，HAVING 防空行覆寫） |
| 2 | silver_facts | `backfill_silver.sql` | `silver.mv_fact_task_vx` | ★ 核心事實表：vx_type 歸屬、五階維度、Cohort 標籤、排除規則 |
| 3 | silver_exclusion | `backfill_exclusion.sql` | `silver.mv_fact_task_vx` | ALTER UPDATE 補 autoComplete 排除旗標 |
| 4 | gold_milestone | `backfill_gold_milestone.sql` | `gold.rmv_l5_milestone_phys` | Todo/Doing/Done Bitmap 快照 |
| 5 | gold_acc | `backfill_gold_acc.sql` | `gold.rmv_l5_acc_phys` | 7 日滾動在途 Bitmap |
| 6 | gold_unified | `backfill_gold.sql` | `gold.rmv_l5_task_completion_phys` | milestone + acc FULL OUTER JOIN 合併主表（**使用中**） |
| 7 | gold_summary_historical | `backfill_gold_summary_historical.sql` | `gold.rmv_l5_task_summary` | V3 邏輯，只寫 `< 2026-04-01` |
| 8 | gold_summary | `backfill_gold_summary.sql` | `gold.rmv_l5_task_summary` | V4 邏輯，只寫 `>= 2026-04-01`（含零開單日 acc 補丁） |

## 注意事項

- 模板佔位符: `{start_ts}`/`{end_ts}`（datetime）、`{start_date}`/`{end_date}`（date），由 `execute_etl.py` 字串替換。
- 步驟 7/8 以 `2026-04-01` 硬邊界互斥分流，修改任一側必須確認邊界不重疊、不遺漏。
- 所有目標表為 ReplacingMergeTree：重跑冪等，但 ORDER BY 內欄位值變更會留殭屍列（需 ALTER DELETE，見 `docs/08_ai_agent/05_Troubleshooting.md` B2）。
- 業務規則詳解: `docs/03_metrics/02_ETL_Transformation_Pipeline.md`；模組地圖: `docs/08_ai_agent/02_Code_Intelligence.md`。
