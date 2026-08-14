# MSSQL → ClickHouse 同步對帳 SQL 手冊

> 用途：每日排程結束後，用純 SQL 查證「相同條件下 MSSQL 有幾筆、ClickHouse 拉回幾筆、完成度多少」。
> 全部查詢都在 ClickHouse 執行（透過 ODBC 代理表讀 MSSQL），不需要另外連 MSSQL 客戶端。
>
> **驗證狀態**：本手冊所有 SQL 區塊皆於 2026-08-14 由腳本逐一抽出、在正式環境實際執行通過
> （建代理表的區塊因含帳密佔位符需人工填入，未自動執行）。

---

## 〇、兩份交付物：先決定要用哪一個

同樣的對帳邏輯做成兩份東西，**擇一即可，不需要兩個都跑**。

| | A. SQL 腳本 | B. Python 報表工具 |
|---|---|---|
| 檔案 | [sql/audit/daily_sync_audit.sql](../sql/audit/daily_sync_audit.sql) | [scripts/etl/tools/audit_sync_progress.py](../scripts/etl/tools/audit_sync_progress.py) |
| 怎麼跑 | 貼進任何 SQL 客戶端 | 命令列 |
| 需要什麼 | 只要能連 ClickHouse | 需 Python 環境 + 專案原始碼 |
| 帳密怎麼給 | **寫在 SQL 裡**（見下方警告） | 讀環境變數 `MSSQL_PASSWORD`，不進 SQL |
| 輸出 | 查詢結果集（19 列） | 主控台報表 + Excel 可開的 CSV |
| 缺漏鍵明細 | 需另外跑範本 C | 自動附在報表下方 |
| 耗時 | 約 170 秒 | 約 170 秒 |
| 適合 | 交接、稽核、臨時查證 | 每日例行產報表 |

**選 A 的時機**：接手的人只有 SQL 客戶端、或需要在稽核場合當場示範查證過程。
**選 B 的時機**：要定期產出報表存檔、或不希望帳密出現在 SQL 語句裡。

### A. SQL 腳本

```
1. 開啟 sql/audit/daily_sync_audit.sql
2. 全文取代 <帳號> 與 <密碼>
3. 整份貼進 ClickHouse 執行
   前段 38 句：建 19 張 ODBC 代理表
   第 39 句  ：主查詢，回傳 19 列對帳結果
   後段 19 句：刪除代理表（表定義含密碼，務必執行）
```

該檔已內建本手冊全部規則，不需要再手動代參數。細節見
[第三節之三](#三之三一次對帳全部-19-張表單一-sql)。

### B. Python 報表工具

```bash
# 產出主控台報表 + CSV
python scripts/etl/tools/audit_sync_progress.py --csv report.csv

# 只看單一張表
python scripts/etl/tools/audit_sync_progress.py --table taskinst

# 排程告警用：未達 100% 或資料停滯時 exit 1
python scripts/etl/tools/audit_sync_progress.py --strict
```

常用參數：

| 參數 | 預設 | 說明 |
|---|---|---|
| `--csv PATH` | 無 | 輸出 UTF-8-BOM 的 CSV，Excel 直接開不會亂碼 |
| `--table KEY` | 全部 | 只對帳單一表（KEY 用第一節的 config key） |
| `--window-days N` | 2 | batch 表回看天數；full 表一律比整表 |
| `--cutoff` | `watermark` | 時間上界；可給 `now` 或 `YYYY-MM-DD HH:MM:SS` |
| `--tolerance-pct` | 0.01 | 容忍落差百分比，吸收 cutoff 邊界效應 |
| `--stale-hours` | 26 | 落後超過幾小時判定停滯（容忍一次排程失敗） |
| `--strict` | 關 | 有問題時 exit 1，供排程告警 |

執行前需先載入環境變數（`MSSQL_PASSWORD` 未設會直接中止並提示，不會靜默失敗）。

輸出的 CSV 結構：主表 19 列 + 總計列 + 備註欄，若有缺漏則在下方附「缺漏鍵明細」區塊。
若 CSV 檔正開在 Excel 中導致寫入失敗，程式會印出錯誤但**不會中斷**——報表內容已完整顯示在
主控台，可直接複製，不必重跑那 170 秒。

> 這支工具**不會**建立任何資料表。（早期版本曾寫入 `bronze._sync_audit`，該功能與資料表
> 已於 2026-08-14 移除並刪除。）

---

## ⚠ 執行前必讀：密碼會明文寫入 ClickHouse 日誌

建立 ODBC 代理表的語句必須帶 MSSQL 帳密，而**本環境的密碼遮蔽規則尚未部署**（2026-08-14 實測：
探針明文完整出現在 `system.query_log`，`Pwd=[HIDDEN]` 筆數為 0）。後果：

| 位置 | 現有明文筆數 | 期間 | 保存期 |
|---|---|---|---|
| `system.query_log.query` | 1,310 | 2026-07-27 起 | **無 TTL，永久** |
| `system.text_log.message` | 753 | 2026-07-27 起 | **無 TTL，永久** |

修法已備妥但未部署：[infra/clickhouse/config.d/query_masking_rules.xml](../infra/clickhouse/config.d/query_masking_rules.xml)，
放進 ClickHouse 的 `config.d/` 並重啟即生效（只影響之後寫入的日誌，既有記錄需另行清理）。

**在遮蔽規則部署前，執行本手冊的 SQL 等同於每次都往永久日誌寫一次明文密碼。**
若不想承擔，改用 `python scripts/etl/tools/audit_sync_progress.py --csv report.csv`（密碼從環境變數讀，不進 SQL）。

---

## 一、參數對照表

每張表要代入的四個參數。**排序鍵請勿憑記憶填寫**，正確值可隨時用下列查詢取得：

```sql
SELECT name, sorting_key FROM system.tables WHERE database = 'bronze' ORDER BY name;
```

| 分類 | 來源表 (MSSQL) | 目的表 (ClickHouse) | 時間欄位 | 排序鍵 | 非唯一鍵 |
|---|---|---|---|---|---|
| 人員/組織 | `APP_SRV_COMMON.dbo.HR_Employee_0503` | `bronze.common_hr_employee` | － | `EmpCode` | |
| 人員/組織 | `APP_SRV_COMMON.dbo.EmpNodeRoleMapping_0503` | `bronze.common_emp_node_role_mapping` | － | `EmpCode, NodeCode` | |
| 人員/組織 | `APP_SRV_COMMON.dbo.EmpOrgInfoMapping_0503` | `bronze.common_emp_org_info_mapping` | － | `EmpCode, Plant, MFGFactoryId` | |
| 人員/組織 | `APP_SRV_COMMON.dbo.EmpUserGroupMapping_0503` | `bronze.common_emp_user_group_mapping` | － | `EmpCode, UserGroupId` | |
| 人員/組織 | `APP_SRV_COMMON.dbo.UserGroup_0503` | `bronze.common_user_group` | － | `UserGroupId` | |
| 人員/組織 | `APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0503` | `bronze.common_process_role_user_mapping` | － | `ID` | |
| 主檔(MDM) | `APP_SRV_COMMON.dbo.MDM_LINE_DESC_MASTER_0503` | `bronze.common_mdm_line_desc_master` | － | `PROD_AREA_ID, LINE_NAME` | **Y** |
| 主檔(MDM) | `APP_SRV_COMMON.dbo.MDM_PROD_AREA_MASTER_0503` | `bronze.common_mdm_prod_area_master` | － | `PROD_AREA_ID` | |
| 主檔(MDM) | `APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER_0503` | `bronze.common_mdm_factory_area_master` | － | `FACTORY` | |
| 主檔(MDM) | `APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER_0503` | `bronze.common_mdm_mfg_site_master` | － | `MFG_SITE` | |
| 主檔(MDM) | `APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER_0503` | `bronze.common_mdm_mfg_plant_master` | － | `MFG_PLANT_ID` | |
| 功能設定 | `APP_SRV_COMMON.dbo.DMPFunctionConfig_0503` | `bronze.common_dmp_function_config` | － | `ID` | |
| 功能設定 | `APP_SRV_COMMON.dbo.DMPFunctionClientMapping_0503` | `bronze.common_dmp_function_client_mapping` | － | `ID` | |
| 流程引擎 | `APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0503` | `bronze.bpm_act_re_procdef` | － | `ID_` | |
| 流程引擎 | `APP_SRV_BPM.dbo.ACT_HI_TASKINST_0503` | `bronze.bpm_act_hi_taskinst` | `LAST_UPDATED_TIME_` | `PROC_INST_ID_, ID_` | |
| 流程引擎 | `APP_SRV_BPM.dbo.ACT_HI_VARINST_0503` | `bronze.bpm_act_hi_varinst` | `CREATE_TIME_` | `PROC_INST_ID_, NAME_, CREATE_TIME_` | **Y** |
| 流程引擎 | `APP_SRV_BPM.dbo.ACT_HI_PROCINST_0503` | `bronze.bpm_act_hi_procinst` | `START_TIME_` | `PROC_INST_ID_` | |
| 流程引擎 | `APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0503` | `bronze.bpm_act_hi_identitylink` | `CREATE_TIME_` | `TASK_ID_, USER_ID_, TYPE_` | **Y** |
| 人員每日匯總 | `APP_SRV_COMMON.dbo.RptCommonKpiUserConfigLog_0503` | `bronze.common_rptkpiuserconfiglog` | － | `empCode, Vx, Plant` | **Y** |

- **時間欄位為「－」** = 全量同步表，對帳時比整表，不加時間條件。
- **非唯一鍵 = Y** = 該表排序鍵在來源端不唯一，必須用範本 B，否則會誤判成大量漏同步。

---

## 二、三條不可違反的對帳規則

違反任一條，算出來的百分比都是錯的。

**規則 1：兩邊必須套用同一個時間上界（cutoff）**
排程執行期間 MSSQL 仍持續進資料。若不凍結上界，分母一直在變，完成度永遠不會到 100%。
cutoff 取該表 watermark 的 `max_data_time`。

**規則 2：ClickHouse 端必須用 `uniqExact(排序鍵)`，不可用 `count()`**
bronze 全是 ReplacingMergeTree，重跑重疊區間會留下尚未合併的重複列。實測 taskinst / procinst
的原始筆數曾達來源的 2 倍，用 `count()` 會算出 200%。

**規則 3：batch 表的下界不可早於 `history_start`（2025-10-01）**
bronze 只保留該日之後的資料，比整段歷史會把「本來就不同步的部分」算成缺口。

---

## 三、SQL 範本

### 步驟 0：建立 ODBC 代理表

以 `taskinst` 為例。欄位定義只需列出對帳會用到的欄位（時間欄位 + 排序鍵欄位）即可，
不必照抄完整結構。

```sql
DROP TABLE IF EXISTS audit_src_taskinst;

CREATE TABLE audit_src_taskinst
(
    ID_                String,
    PROC_INST_ID_      String,
    LAST_UPDATED_TIME_ DateTime
)
ENGINE = ODBC(
    'DSN=MSSQL_DSN;Database=APP_SRV_BPM;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no',
    'dbo',
    'ACT_HI_TASKINST_0503'
);
```

> `MARS_Connection=no` 不可省略——省略會導致 ODBC 連線池毒化（IMC06「connection is broken」），
> 一旦發生只能重啟 bridge：`docker exec clickhouse-server-odbc pkill -f clickhouse-odbc-bridge`。

---

### 範本 A：唯一鍵表對帳（大多數表用這個）

```sql
SELECT
    'ACT_HI_TASKINST' AS `來源表`,
    (SELECT count() FROM audit_src_taskinst
      WHERE LAST_UPDATED_TIME_ >= ((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                                     WHERE table_name = 'bronze.bpm_act_hi_taskinst') - INTERVAL 2 DAY)
        AND LAST_UPDATED_TIME_ <   (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                                     WHERE table_name = 'bronze.bpm_act_hi_taskinst')
    ) AS `來源端筆數`,
    (SELECT uniqExact(PROC_INST_ID_, ID_) FROM bronze.bpm_act_hi_taskinst
      WHERE LAST_UPDATED_TIME_ >= ((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                                     WHERE table_name = 'bronze.bpm_act_hi_taskinst') - INTERVAL 2 DAY)
        AND LAST_UPDATED_TIME_ <   (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                                     WHERE table_name = 'bronze.bpm_act_hi_taskinst')
    ) AS `目的端筆數`,
    `來源端筆數` - `目的端筆數` AS `未同步筆數`,
    round(`目的端筆數` * 100.0 / `來源端筆數`, 4) AS `同步百分比`
SETTINGS max_execution_time = 1800;
```

實測輸出：

```
來源表          | 來源端筆數 | 目的端筆數 | 未同步筆數 | 同步百分比
ACT_HI_TASKINST | 126323     | 126323     | 0          | 100.0
```

> **不要改用 `WITH ... AS cutoff` 的寫法。** ClickHouse 的純量 CTE 無法在巢狀子查詢內解析，
> 會直接噴 SYNTAX_ERROR（已實測）。所以這裡刻意把 cutoff 子查詢內聯重複四次。

全量同步表（時間欄位為「－」）把兩段 `WHERE` 整個拿掉即可，其餘不變。

---

### 範本 B：非唯一鍵表對帳（4 張標 Y 的表用這個）

差別是**來源端也要按同一組鍵去重**，兩邊基準才一致。

```sql
SELECT
    'ACT_HI_IDENTITYLINK' AS `來源表`,
    (SELECT count() FROM audit_src_identitylink
      WHERE CREATE_TIME_ >= ((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                               WHERE table_name = 'bronze.bpm_act_hi_identitylink') - INTERVAL 2 DAY)
        AND CREATE_TIME_ <   (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                               WHERE table_name = 'bronze.bpm_act_hi_identitylink')
    ) AS `來源端原始列數`,
    (SELECT uniqExact(TASK_ID_, USER_ID_, TYPE_) FROM audit_src_identitylink
      WHERE CREATE_TIME_ >= ((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                               WHERE table_name = 'bronze.bpm_act_hi_identitylink') - INTERVAL 2 DAY)
        AND CREATE_TIME_ <   (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                               WHERE table_name = 'bronze.bpm_act_hi_identitylink')
    ) AS `來源端去重後`,
    (SELECT uniqExact(TASK_ID_, USER_ID_, TYPE_) FROM bronze.bpm_act_hi_identitylink
      WHERE CREATE_TIME_ >= ((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                               WHERE table_name = 'bronze.bpm_act_hi_identitylink') - INTERVAL 2 DAY)
        AND CREATE_TIME_ <   (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                               WHERE table_name = 'bronze.bpm_act_hi_identitylink')
    ) AS `目的端筆數`,
    `來源端去重後` - `目的端筆數` AS `未同步筆數`,
    round(`目的端筆數` * 100.0 / `來源端去重後`, 4) AS `同步百分比`
SETTINGS max_execution_time = 1800;
```

實測輸出：

```
來源表              | 來源端原始列數 | 來源端去重後 | 目的端筆數 | 未同步筆數 | 同步百分比
ACT_HI_IDENTITYLINK | 1283687        | 848876       | 848875     | 1          | 99.9999
```

注意「來源端原始列數 1,283,687」與「去重後 848,876」的差距（33%）——這是排序鍵折疊，**不是漏同步**。
若拿原始列數當分母，這張表會被誤判成只完成 66%。

> 來源端 `uniqExact` 不會下推到 MSSQL，需把欄位撈回 ClickHouse 才能算，500 萬列約 100～155 秒。
> 這是這 4 張表比其他表慢很多的原因。日常請把窗口控制在 1～2 天。

---

### 範本 C：缺漏鍵明細（未同步筆數 > 0 時查這個）

回答「到底缺了哪幾筆」。

```sql
SELECT
    PROC_INST_ID_, ID_,
    min(LAST_UPDATED_TIME_) AS `來源最早時間`,
    count() AS `來源列數`
FROM audit_src_taskinst
WHERE LAST_UPDATED_TIME_ >= ((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                               WHERE table_name = 'bronze.bpm_act_hi_taskinst') - INTERVAL 2 DAY)
  AND LAST_UPDATED_TIME_ <   (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                               WHERE table_name = 'bronze.bpm_act_hi_taskinst')
GROUP BY PROC_INST_ID_, ID_
HAVING (PROC_INST_ID_, ID_) NOT IN (
    SELECT PROC_INST_ID_, ID_ FROM bronze.bpm_act_hi_taskinst
    WHERE LAST_UPDATED_TIME_ >= ((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                                   WHERE table_name = 'bronze.bpm_act_hi_taskinst') - INTERVAL 2 DAY)
      AND LAST_UPDATED_TIME_ <   (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL
                                   WHERE table_name = 'bronze.bpm_act_hi_taskinst')
    GROUP BY PROC_INST_ID_, ID_)
ORDER BY `來源最早時間`
LIMIT 20
SETTINGS max_execution_time = 1800;
```

換表時把 `PROC_INST_ID_, ID_` 換成該表的排序鍵、時間欄位與表名一併替換即可。
這條 `NOT IN` 子查詢很貴，**只在確認有落差時才跑**。

---

### 範本 D：新鮮度（完成度 100% 不代表沒有落後）

cutoff 取自 watermark，所以同步若整個卡住，watermark 不前進、cutoff 也不前進，
完成度會一路回報 100%，完全看不出資料早已停滯。**必須另外查這條。**

```sql
SELECT
    (SELECT toDateTime(max(LAST_UPDATED_TIME_)) FROM bronze.bpm_act_hi_taskinst) AS `CH最新`,
    (SELECT toDateTime(max(LAST_UPDATED_TIME_)) FROM audit_src_taskinst)         AS `MSSQL最新`,
    dateDiff('second', `CH最新`, `MSSQL最新`) AS `落後秒數`
SETTINGS max_execution_time = 1800;
```

實測輸出（`max()` 有下推，很快）：

```
CH最新                    | MSSQL最新                 | 落後秒數
2026-05-19 23:15:35+08:00 | 2026-05-19 23:15:35+08:00 | 0
```

判讀：落後秒數 > 26 小時（93,600 秒）代表排程可能已連續失敗，需立即檢查。

---

### 三之三：一次對帳全部 19 張表（單一 SQL）

前面的範本一次只處理一張表。若要一次比完全部，用 **[sql/audit/daily_sync_audit.sql](../sql/audit/daily_sync_audit.sql)**——
該檔已用 `UNION ALL` 把 19 張表併成單一查詢，回傳單一結果集。

```
使用方式：
  1. 全文取代 <帳號> 與 <密碼>
  2. 整份貼進 ClickHouse 執行（前段建 19 張代理表、中段查詢、末段清理）
  3. 實測耗時約 170 秒
```

實測輸出（2026-08-14，batch 表窗口 2 天）：

```
分類            來源表                                              來源筆數     目的筆數    未同步    百分比
人員/組織       APP_SRV_COMMON.dbo.HR_Employee_0503                  151,196    151,196        0   100.0%
人員/組織       APP_SRV_COMMON.dbo.EmpNodeRoleMapping_0503             4,633      4,633        0   100.0%
人員/組織       APP_SRV_COMMON.dbo.EmpOrgInfoMapping_0503              2,368      2,368        0   100.0%
人員/組織       APP_SRV_COMMON.dbo.EmpUserGroupMapping_0503            2,083      2,083        0   100.0%
人員/組織       APP_SRV_COMMON.dbo.UserGroup_0503                          9          9        0   100.0%
人員/組織       APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0503        44,061     44,061        0   100.0%
主檔(MDM)       APP_SRV_COMMON.dbo.MDM_LINE_DESC_MASTER_0503          16,651     16,651        0   100.0%
主檔(MDM)       APP_SRV_COMMON.dbo.MDM_PROD_AREA_MASTER_0503           1,105      1,105        0   100.0%
主檔(MDM)       APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER_0503          123        123        0   100.0%
主檔(MDM)       APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER_0503               11         11        0   100.0%
主檔(MDM)       APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER_0503             499        499        0   100.0%
功能設定        APP_SRV_COMMON.dbo.DMPFunctionConfig_0503                484        484        0   100.0%
功能設定        APP_SRV_COMMON.dbo.DMPFunctionClientMapping_0503          58         58        0   100.0%
流程引擎(BPM)   APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0503                      583        583        0   100.0%
流程引擎(BPM)   APP_SRV_BPM.dbo.ACT_HI_TASKINST_0503                 126,323    126,323        0   100.0%
流程引擎(BPM)   APP_SRV_BPM.dbo.ACT_HI_VARINST_0503                1,309,834  1,309,834        0   100.0%
流程引擎(BPM)   APP_SRV_BPM.dbo.ACT_HI_PROCINST_0503                  51,189     51,189        0   100.0%
流程引擎(BPM)   APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0503             848,876    848,875        1  99.9999%
人員每日匯總    APP_SRV_COMMON.dbo.RptCommonKpiUserConfigLog_0503      2,315      2,315        0   100.0%
```

該檔已內建本手冊的三條規則：cutoff 逐表取自各自的 watermark、CH 端一律 `uniqExact(排序鍵)`、
4 張非唯一鍵表的來源端也做同鍵去重、batch 表下界套 `greatest(cutoff - 2 天, history_start)`。
**若日後 `sync_tables.yaml` 增減表或 bronze 排序鍵變動，該檔需同步更新**（排序鍵請用第一節的
`system.tables` 查詢取得，勿憑記憶填寫）。

---

### 步驟 9：清理

代理表用完即刪，避免殘留（表定義內含密碼，`SHOW CREATE TABLE` 可讀出）。

```sql
DROP TABLE IF EXISTS audit_src_taskinst;
DROP TABLE IF EXISTS audit_src_identitylink;
```

---

## 四、判讀規則：什麼算正常

| 情況 | 判定 | 處置 |
|---|---|---|
| 未同步筆數 = 0 | 正常 | 無 |
| 4 張非唯一鍵表用範本 B 後 = 0 | 正常 | 無 |
| 未同步筆數為個位數、落後秒數 = 0 | 多半是 cutoff 邊界效應 | 用範本 C 確認鍵值後放行 |
| 未同步筆數大量、落後秒數 = 0 | 真的漏同步 | 查該表當日 sync log |
| 落後秒數 > 93,600 | 排程停擺 | 優先處理，此時完成度數字無意義 |

---

## 五、已知的 4 張非唯一鍵表（不是 bug，勿修）

| 表 | 折疊比例 | 原因 | 影響 |
|---|---|---|---|
| `varinst` | 13.0% | 排序鍵缺 `TASK_ID_`，同流程同名同時間的任務層級變數被折疊 | 見下方說明 |
| `identitylink` | 33.9% | `participant` 類 `TASK_ID_` 為空，同一人所有流程擠同一桶 | 無下游引用 |
| `mdm_line_desc` | 10.1% | 來源同一 `(PROD_AREA_ID, LINE_NAME)` 有多列 | 僅 `LINE_DESC` 顯示欄位，JOIN 鍵不受影響 |
| `kpi_user_config_log` | 99.5% | 來源是按 `ConfigDate` 的歷史 log，排序鍵不含日期，只留每組最後一筆 | 無下游引用 |

四張表在**鍵層級都是 100%、0 筆缺漏**（2026-08-14 實測）。

### varinst 的已知影響（已評估，決定不修）

[backfill_exclusion.sql](../sql/etl/dml/backfill_exclusion.sql) 按 `TASK_ID_` 查 `autoComplete=1`，
但排序鍵不含 `TASK_ID_`，故部分 task_id 被折疊掉：

- 一日內 MSSQL 有 26,805 個 `autoComplete=1` 的 task_id，CH 只剩 13,827（覆蓋率 51.58%）
- 但掉失的 12,978 筆中，**12,974 筆已被 `system_bypass` 規則攔下**
- 真正漏排除、被算進 KPI 的只有 **4 筆**（同日總任務 108,425 筆，誤差 0.004%）

修法是把排序鍵改成 `(PROC_INST_ID_, NAME_, TASK_ID_, CREATE_TIME_)`，但需重建表 + 全量回填，
性價比不成立，故維持現狀並記錄於此。

### identitylink 缺漏鍵的實例（範本 C 的典型輸出）

```
TASK_ID_ | USER_ID_ | TYPE_       | 來源最早時間              | 來源列數
(空)     | 32717724 | participant | 2026-05-18 17:01:42+08:00 | 12
```

查證後確認**資料並未遺失**：該鍵在 CH 有 5 列，但 `CREATE_TIME_` 都在 2026-05-17 06:31 以前。
原因是排序鍵不含時間，該使用者 05-18 的 12 列被折疊進 05-17 的倖存列，用時間窗口就撈不到。
屬排序鍵設計的副作用，非漏拉。

---

## 六、維護須知：什麼情況下要更新這些檔案

兩份交付物都把「19 張表的參數」寫死在裡面，**來源異動時必須同步更新，否則會漏檢或誤判**：

| 異動 | 要改哪裡 |
|---|---|
| `sync_tables.yaml` 增減表 | SQL 腳本的代理表與 UNION 區塊；Python 工具的 `TABLE_CATEGORIES` |
| bronze 表排序鍵變更 | 兩者的排序鍵（用第一節的 `system.tables` 查詢取得，勿憑記憶填） |
| 新表的排序鍵在來源端非唯一 | SQL 腳本改用範本 B 的寫法；Python 工具加進 `NON_UNIQUE_KEY_TABLES` |
| `history_start` 調整 | 兩者的下界 `greatest(cutoff - N 天, history_start)` |

Python 工具的排序鍵是執行時從 `system.tables` 動態查的，排序鍵變更會自動跟上；
**但 SQL 腳本是寫死的**，這是它唯一需要人工維護的地方。

---

## 七、驗證紀錄

| 項目 | 驗證方式 | 結果 | 日期 |
|---|---|---|---|
| 本手冊 SQL 區塊 | 腳本逐一抽出並執行 | 6 個可執行區塊全通過（建表區塊含佔位符跳過） | 2026-08-14 |
| `daily_sync_audit.sql` | 逐句執行整個檔案 | 58/58 通過，主查詢回傳 19 列，清理後零殘留 | 2026-08-14 |
| `audit_sync_progress.py` | 全表實跑 + CSV 寫入單元測試 | 19 列正確；CSV 含 BOM、表頭、缺漏鍵區塊；鎖檔情境不崩潰 | 2026-08-14 |
