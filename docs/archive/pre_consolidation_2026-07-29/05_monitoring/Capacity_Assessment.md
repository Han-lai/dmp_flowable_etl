# 容量評估：MSSQL → ClickHouse 空間與時間成本

**量測日期**：2026-07-27
**量測對象**：production `bronze`（CH）、`APP_SRV_BPM`（MSSQL 來源）
**資料涵蓋**：2025-10-08 ~ 2026-05-19（約 7.5 個月）

---

## 1. 結論摘要

| 項目 | 實測值 |
|---|---|
| MSSQL 來源端（同步的 4 張事實表） | **224.3 M 列 / 約 65 GB** |
| ClickHouse bronze 落地 | **約 2.55 GB**（未壓縮約 34 GB） |
| 全量重建耗時 | **約 2 小時 20 分** |
| 每日增量耗時 | **約 3 分鐘** |
| 資料級別 | **GB 級**（距 1 TB 尚差 15 倍，距 1 PB 差約 15,400 倍） |

這是標準的 GB 級數倉。磁碟不是瓶頸，**真正的成本在同步吞吐**（ODBC 逐批往返），與資料「大小」的關聯低於與「批次數量」的關聯。

---

## 2. MSSQL 來源端

以 `sys.dm_db_partition_stats` 量測（唯讀）。

| MSSQL 表 | 列數 | reserved |
|---|---|---|
| `ACT_HI_VARINST_0503` | 87,916,217 | 33.5 GB |
| `ACT_HI_IDENTITYLINK_0503` | 126,882,194 | 25.7 GB |
| `ACT_HI_TASKINST_0503` | 6,619,852 | 3.6 GB |
| `ACT_HI_PROCINST_0503` | 2,930,672 | 2.1 GB |
| **合計** | **224,348,935** | **約 65 GB** |

`APP_SRV_COMMON` 的 15 張維度表無法量測（`APP_SRV_BPM` 帳號在該庫沒有 `VIEW DATABASE STATE` 權限），但從 CH 端反推未壓縮僅約 67 MB，量級可忽略。

**同步完整性交叉驗證**：

| 表 | MSSQL 列數 | CH 去重後列數 | 結果 |
|---|---|---|---|
| taskinst | 6,619,852 | 6,619,852 | 完全一致 |
| procinst | 2,930,672 | 2,930,672 | 完全一致 |

---

## 3. ClickHouse 落地與壓縮

| 表 | MSSQL | CH 落地 | CH 未壓縮 | 壓縮比 |
|---|---|---|---|---|
| varinst | 33.5 GB | 1.17 GB | 17.32 GB | **29×** |
| identitylink | 25.7 GB | 0.65 GB | 13.38 GB | **40×** |
| taskinst | 3.6 GB | 0.44 GB | 2.16 GB | 8× |
| procinst | 2.1 GB | 0.27 GB | 1.22 GB | 8× |
| 15 張維度表 | — | 4.4 MB | 67 MB | 15× |
| **bronze 全庫** | | **約 2.55 GB** | **約 34 GB** | |

identitylink 壓到 40 倍是因為只有 4 個窄欄位且重複值極多（`TYPE_` 基數個位數）。taskinst / procinst 欄位寬、內容分散，只有 8 倍。

> **注意**：CH 上另有 `bronze_0717`、`bronze_0202`、`bronze_backup` 三套歷史副本，各佔 0.1 ~ 2 GB。做磁碟規劃時需一併計入，或先確認是否可刪。

---

## 4. 單位成本模型

### 4.1 空間：每列落地成本

取自**沒有重複的月份**（2025-10 ~ 2026-02）：

| 表 | 乾淨月列數 | 乾淨月落地 | bytes/row |
|---|---|---|---|
| varinst | 22,094,462 | 242.7 MB | **11.5 B** |
| identitylink | 49,910,224 | 174.9 MB | **3.7 B** |
| taskinst | 2,156,217 | 139.4 MB | **67.8 B** |
| procinst | 802,566 | 72.0 MB | **94.1 B** |

### 4.2 時間：同步吞吐

取自 2026-07-20 ~ 07-21 的建置 log（`scripts/etl/*.log`）：

| 表 | 實測 | rows/s |
|---|---|---|
| identitylink | 87.6 M 列 / 2,467 s | **35,500** |
| taskinst | 5.3 M 列 / 182 s | **29,000** |
| varinst | 81.1 M 列 / 4,361 s | **18,600** |
| procinst | 2.9 M 列 / 215 s | **13,600** |

---

## 5. 兩種業務量區間

2026-03 起業務量出現階躍（產線陸續上線），去重後仍有約 **4.4 倍**成長。估算時必須分開，否則誤差達數倍。

| 表 | 低量期每月<br>(2025-10 ~ 2026-02) | 高量期每月<br>(2026-03 起) |
|---|---|---|
| varinst | 65 MB / 5.3 分 | 260 MB / 21.2 分 |
| identitylink | 47 MB / 6.0 分 | 60 MB / 8.0 分 |
| taskinst | 37 MB / 0.3 分 | 130 MB / 1.2 分 |
| procinst | 19 MB / 0.3 分 | 82 MB / 1.1 分 |
| 15 維度表（每次必跑） | 4.4 MB / 0.3 分 | 4.4 MB / 0.3 分 |
| **合計** | **約 170 MB / 12.5 分** | **約 530 MB / 32 分** |

**模型驗證**：現有 7.5 個月 = 5 個低量月 + 2.5 個高量月
- 時間：5 × 12.5 + 2.5 × 32 = 142 分 → log 實測加總約 140 分，**誤差 < 2%**
- 空間：5 × 170 + 2.5 × 530 = 2.15 GB → 實際 2.53 GB（含 Mar/Apr 的重複殘留），一致

---

## 6. 常見情境估算

| 情境 | 時間 | 落地空間 |
|---|---|---|
| 重建現有全量（7.5 個月） | 約 2 h 20 m | 約 2.2 GB |
| 逐月回填 · 低量月 | 約 13 分 | 約 170 MB |
| 逐月回填 · 高量月 | 約 32 分 | 約 530 MB |
| 未來每新增一個月（高量常態） | 約 32 分 | 約 530 MB |
| 每日增量（`daily_etl_wrapper.sh` Step 1） | 約 3 分 | 約 18 MB |
| 往前多補 6 個月歷史（假設低量） | 約 75 分 | 約 1.0 GB |

「每日約 3 分」為 2026-07-27 單日 Phase 2 全表實測（19 張表，wall time 3 分 18 秒）。其中絕大部分是固定成本，與當日資料量無關。

---

## 7. 資料級別對照

| 級別 | 量級 | 本專案 |
|---|---|---|
| GB 級 | 1 GB ~ 1 TB | **目前位置**（來源 65 GB / 落地 2.55 GB） |
| TB 級 | 1 TB ~ 1 PB | 尚差 15 倍才到 1 TB |
| PB 級 | ≥ 1 PB | 尚差約 15,400 倍 |

以高量期速率推算成長到 1 PB 所需時間：

| 側 | 每月增量 | 到 1 PB |
|---|---|---|
| MSSQL 來源 | 約 14.6 GB | 約 5,700 年 |
| ClickHouse 落地 | 約 0.53 GB | 約 165,000 年 |

即使業務量再成長 100 倍（每月 1.46 TB 來源端），到 1 PB 仍需約 57 年。**本系統在可預見的生命週期內不會進入 TB 級以上規模**，容量規劃口徑應定為「GB 級、單節點、來源端成長率約 15 GB/月」。

---

## 8. 會讓估算失準的三個因素

**8.1 維度表不隨時間窗縮放**
`--start` / `--end` 對 15 張 `strategy: full` 的表完全無效，每次 `--table all` 都整批重抓 + RENAME 換表。只同步一天也要付這約 19 秒加建表成本。要省需改跑單表（如 `--table taskinst`）。

**8.2 空批次仍有成本**
`step_days: 2` 表示每月產生約 15 個批次，即使 0 筆也要建 temp table、發 ODBC 查詢。建置 log 中曾出現 42 個批次僅 10 個有資料，卻仍耗時 3 分 17 秒。回填時應將 `--end` 訂在真實資料尾端，不要無腦拉到今天。

**8.3 重跑會實際佔用空間**
ReplacingMergeTree 只在 merge 當下去重，重疊視窗重跑產生的舊版本列會長期留在磁碟上並被查詢掃到。實測重複倍率：

| 表 | 2026-03 | 2026-04 | 2026-05 |
|---|---|---|---|
| varinst | 1.67× | 1.98× | 1.10× |
| identitylink | 1.74× | 1.97× | 1.21× |
| taskinst | 1.05× | 1.00× | 1.18× |
| procinst | 1.00× | 1.00× | 1.10× |

varinst 2026-04 分區因此從約 260 MB 膨脹至 505 MB。處理方式見下節。

---

## 9. 維護建議

**每個月只同步一次**。`execute_etl.py` 會跳過已標記 SUCCESS 的相同視窗，但 `sync_unified_odbc.py` 不會——重跑同一段時間窗會實際重新灌入資料。

**大量回填後執行 OPTIMIZE**。四張表皆為 `PARTITION BY toYYYYMM(...)`，可逐分區處理，成本可控：

```sql
OPTIMIZE TABLE bronze.bpm_act_hi_varinst PARTITION 202604 FINAL;
```

避免整表 `OPTIMIZE TABLE ... FINAL`（會重寫成單一 part，需要約等同表大小的臨時磁碟）。

**時機**：大範圍回填後、對帳或 UAT 匯出前、發現某分區列數異常時。
**不要**放進每日排程——每日增量只產生小 part，背景 merge 足以處理。
**不要**與每日同步同時執行，會搶佔 IO 與 merge pool。

> `OPTIMIZE` 為重寫資料的操作，執行前請依 CLAUDE.md 鐵律向使用者確認。

---

## 10. 重新量測方式

數值變動時可依下列查詢校正本文件。連線資訊一律取自環境變數，勿寫死。

**MSSQL 來源端大小**（透過 CH 的 `odbc()`，唯讀）：

```sql
SELECT o.name AS tbl,
       sum(ps.row_count)                             AS rows,
       round(sum(ps.reserved_page_count)*8/1024., 1) AS reserved_mb
FROM odbc('<conn>', 'sys', 'dm_db_partition_stats') AS ps
INNER JOIN odbc('<conn>', 'sys', 'objects') AS o ON ps.object_id = o.object_id
WHERE ps.index_id IN (0, 1) AND o.type = 'U '
GROUP BY o.name ORDER BY sum(ps.reserved_page_count) DESC;
```

`<conn>` 格式與 `sync_unified_odbc.py` 的 `build_odbc_conn()` 相同：
`DSN=${ODBC_DSN};Database=APP_SRV_BPM;Uid={${MSSQL_USER}};Pwd={${MSSQL_PASSWORD}};MARS_Connection=no`

**CH 落地大小與逐月分佈**：

```sql
SELECT table, partition, sum(rows) AS rows,
       round(sum(bytes_on_disk)/1048576., 1)          AS disk_mb,
       round(sum(data_uncompressed_bytes)/1048576., 1) AS raw_mb,
       count() AS parts
FROM system.parts
WHERE database = 'bronze' AND active
GROUP BY table, partition ORDER BY table, partition;
```

**重複倍率**（以 varinst 為例，其餘表替換排序鍵與時間欄）：

```sql
SELECT toYYYYMM(CREATE_TIME_) AS ym, count() AS raw,
       uniqExact((PROC_INST_ID_, NAME_, CREATE_TIME_)) AS dedup
FROM bronze.bpm_act_hi_varinst GROUP BY ym ORDER BY ym;
```

各表排序鍵：
| 表 | 排序鍵 | 分區時間欄 |
|---|---|---|
| varinst | `(PROC_INST_ID_, NAME_, CREATE_TIME_)` | `CREATE_TIME_` |
| identitylink | `(TASK_ID_, USER_ID_, TYPE_)` | `CREATE_TIME_` |
| taskinst | `(PROC_INST_ID_, ID_)` | `START_TIME_` |
| procinst | `PROC_INST_ID_` | `START_TIME_` |

**同步耗時**：`bronze._sync_watermark` 只保留每張表**最後一次**的 `row_count` / `duration_ms`，不是歷史累積。完整的建置耗時記錄在 `scripts/etl/*.log`（2026-07-20 ~ 07-21 建置期間產生，注意這批 log 打的是 `bronze_0717` 沙盒）。

---

*維護單位：AIT / Data Engineering*
