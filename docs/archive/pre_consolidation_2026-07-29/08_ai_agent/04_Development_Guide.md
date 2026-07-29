# Development Guide（開發規範）

**建立日期**: 2026-07-03｜**適用**: 所有未來 AI Session 與人類開發者
**深度教學**: 新增指標的完整 SOP 已在 [docs/03_metrics/04_Developer_Guide_New_Metrics.md](../03_metrics/04_Developer_Guide_New_Metrics.md) 與 [docs/06_Data_Engineer_Handover.md](../06_Data_Engineer_Handover.md) 第八部分，本文不重複，只列規範與檢查清單。

---

## 1. 慣例（從現有程式碼歸納，✅ 已驗證）

### 檔案與命名
- ETL 業務邏輯 SQL → `sql/etl/dml/backfill_<層>_<主題>.sql`；DDL → `sql/etl/schema/<序號>_<層>_<主題>.sql`。
- SQL 模板佔位符只有四個：`{start_ts}`、`{end_ts}`（datetime 秒級）、`{start_date}`、`{end_date}`（日期），由 `execute_etl.py` 字串替換。
- 表命名：bronze=`<來源系統>_<原表小寫>`；silver=`mv_*`；gold=`rmv_*`（歷史命名，實際都是物理表）。
- Cube 檔案 `cube_<主題>.js`，cube 名 PascalCase（如 `L5TaskPeriodic`）。
- Python：環境變數讀連線設定（**嚴禁寫死 IP/密碼**）、argparse CLI、logging 模組（sync）或 print（etl）。中文 docstring 說明「為什麼」。

### 修改流程鐵律
1. **改業務邏輯 = 改 DML SQL**；Python 引擎只管「怎麼跑」，不放業務規則。
2. **新增 pipeline 階段** = 在 `pipeline_config.yaml` 加 step（phase_id + template + target_table），不改 execute_etl.py。
3. **新增同步表** = 在 `sync_tables.yaml` 加 entry（含顯式 `engine_ddl`，必填）+ `sql/etl/schema/` 加 DDL + `setup_schema.py` 部署。
4. **改 Silver 邏輯後必須回填**：確認影響時間範圍，用 `--backfill --start ... --end ... --low-ram` 重算，並確認 Gold 下游是否需連動重算/清理（注意 ORDER BY 殭屍列問題，KB §3）。
5. **改 Gold summary** 必須同時檢查 V3/V4 兩支 SQL 的 2026-04-01 邊界互斥。
6. **費率類 measure** 一律 `floor(qty*100/total)`（Rule 2），禁止 round()。

### Commit 與版控（使用者明確要求）
- Commit 訊息用**英文** conventional commits（`fix(etl):` / `feat(cube):` / `docs:` …），現有 git log 為範本。
- **絕不自動 push**。push GitHub 前：diff 檢查無 IP/密碼、身份必須是 `Han-lai <sh41bee@gmail.com>`；GitLab 用公司身份。
- 目前已知風險：memory-bank 等 5 個追蹤檔含 IP/舊密碼（Assessment R1），推 GitHub 前必須先處理。

## 2. 測試

- 單元測試：`python -m pytest tests/ -v`（Windows 開發機，venv：`.venv/`）。
- 測試對應：改 `execute_etl.py` 視窗/OOM 邏輯 → `test_etl_windows.py`、`test_execute_etl_oom.py`；改 sync → `test_sync_odbc.py`;改 pipeline_config → `test_pipeline_config.py`;改 API → `test_api_main.py`。
- 資料正確性驗證（比單測更重要）：
  - `python scripts/etl/execute_etl.py --status`（watermark/checkpoint/筆數三面板）。
  - CH vs MSSQL 對帳：`scripts/etl/audit_done_details.py`；歷史基準數值在 memory-bank 與 `prd_audit/`（如 2025-12-31 WJ2 WJ-S28: Todo 9 / Doing 5 / Done 186 / Total 200）。
  - **對帳時 MSSQL 端查詢必須複製 Silver 的 vx_type 覆蓋規則**（MoNumber 前綴 + NPE），否則 V3 計數虛高（2026-06-09 教訓）。

## 3. Review Checklist（AI 自查用）

**SQL 變更**
- [ ] 佔位符只用四個標準變數？模板可被字串替換安全處理？
- [ ] 有時間視窗過濾（增量安全）？重跑冪等（ReplacingMergeTree 去重鍵覆蓋所有會變動的維度）？
- [ ] JOIN ReplacingMergeTree 是否用 argMax 或 FINAL 防翻倍？
- [ ] String LEFT JOIN 結果是否需要 NULLIF(x,'')？
- [ ] 記憶體：大 JOIN/GROUP BY 是否在 low-ram 模式可過（500MB spill）？
- [ ] 週/月聚合是否處理視窗邊界擴張？
- [ ] 需要 `SETTINGS allow_experimental_analyzer = 0` 嗎（複合 JOIN 條件時）？

**Python 變更**
- [ ] 無寫死 IP/密碼？連線走環境變數？
- [ ] 失敗會不會靜默（exit code、checkpoint 標記正確）？
- [ ] TRUNCATE/DROP/DELETE 類操作有沒有確認影響範圍？

**Cube 變更**
- [ ] filter 保持在內層 SQL（FILTER_PARAMS pushdown），沒把函數包在被過濾欄位上（會破壞主鍵索引）？
- [ ] 費率用 floor()？
- [ ] 讀 summary 表要 FINAL？

**危險操作（先停下來向使用者確認）**
- MSSQL 任何寫入/DDL（絕對禁止）；ClickHouse `DROP`/`TRUNCATE`/`ALTER DELETE`；`execute_etl.py --reset`；git push；改 `infra/.env`。
