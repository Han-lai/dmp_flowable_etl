# MSSQL → ClickHouse 資料匯入方案比較

## 一、比較背景說明

本次評估針對 **同一批 MSSQL 原始資料**，比較三種不同匯入 ClickHouse 的方案：

| 方案 | 說明 |
|------|------|
| **ODBC Bridge (最終採用)** | 原生 C++ 驅動結構，具備極高吞吐量且無多餘儲存損耗 |
| **JDBC Bridge** | 直接以 JDBC query 將資料寫入 ClickHouse，結構貼近 MSSQL 原始 schema |
| **Airbyte** | 透過 Airbyte 同步 MSSQL 至 ClickHouse，內建增量同步、UI 管理與 metadata 欄位 |

---

## 二、資料一致性與儲存空間比較

**總結：**
- 共 16 張表
- 15 張表筆數完全一致
- 1 張表差 1 筆（推測與同步時間點差異有關）

| 表名 | 筆數 (JDBC) | 筆數 (Airbyte) | 差異 | JDBC 大小 | Airbyte 大小 | 空間增幅 |
|------|-------------|----------------|------|-----------|--------------|----------|
| ACT_HI_IDENTITYLINK | 539,351 | 539,351 | 0 | 9.47 MB | 22.65 MB | 2.4x |
| ACT_HI_VARINST | 628,278 | 628,278 | 0 | 17.54 MB | 32.85 MB | 1.9x |
| FlowableTaskStats | 732,345 | 732,345 | 0 | 80.43 MB | 106.41 MB | 1.3x |
| HR_Employee | 125,667 | 125,667 | 0 | 23.79 MB | 23.28 MB | 1.0x |
| ACT_HI_TASKINST | 48,034 | 48,034 | 0 | 3.96 MB | 5.16 MB | 1.3x |
| ProcessRoleUserMapping | 31,298 | 31,298 | 0 | 0.28 MB | 1.05 MB | 3.8x |
| ACT_HI_PROCINST | 16,075 | 16,075 | 0 | 1.30 MB | 1.72 MB | 1.3x |
| ACT_RE_PROCDEF | 7,249 | 7,249 | 0 | 0.11 MB | 0.29 MB | 2.5x |
| 其他 8 張小表 |  一致 |  一致 | 0 | < 0.1 MB | < 0.1 MB | 2～4x |
| **UserGroup** | **9** | **8** | **-1** | 0.5 KB | 1.3 KB | - |


---

## 三、Airbyte 額外欄位說明

Airbyte 於每張表中自動新增以下 metadata 欄位：

| 欄位名稱 | 用途 |
|----------|------|
| `_airbyte_raw_id` | 每筆資料的唯一識別碼，用於追蹤與除錯 |
| `_airbyte_extracted_at` | 資料擷取時間，可作為增量同步 watermark |
| `_airbyte_meta` | 同步過程的 metadata（錯誤訊息、狀態等） |
| `_airbyte_generation_id` | 同步批次識別碼，用於增量與版本控管 |

---

## 四、同步時間與效能比較

| 方案 | 資料來源 | 筆數 | 耗時 | 平均速度 |
|------|----------|------|------|----------|
| **ODBC Bridge** | APP_SRV_BPM 等 | 約 5,290萬 | **約 9.7 分鐘** | **~90,218 筆/秒** |
| **JDBC Bridge** | APP_SRV_BPM + APP_SRV_COMMON | 2,134,433 | **1 分 5 秒** | 32,837 筆/秒 |
| Airbyte | APP_SRV_BPM | 1,238,987 | 2 分 45 秒 | 7,508 筆/秒 |
| Airbyte | APP_SRV_COMMON | 895,446 | 5 分 33 秒 | 2,689 筆/秒 |
| **Airbyte 合計** | 兩個來源 | 2,134,433 | **8 分 18 秒** | 4,285 筆/秒 |

---

## 五、整體比較總覽

| 比較項目 | ODBC Bridge (採用) | JDBC Bridge | Airbyte |
|----------|----------------|-------------|---------|
| 平均速度 | **~90,218 筆/秒** | 32,837 筆/秒 | 4,285 筆/秒 |
| 儲存空間 | **1.0x (無損耗)** | 1.0x (無損耗) | 1.3x ~ 3.8x |
| 驅動層級 | Native C++ | JVM JDBC | Containerized |
| 增量同步 | 自行開發 (Watermark) | 自行開發 | 內建支援 |
| Metadata | 無多餘欄位 | 無多餘欄位 | 有 |

---

## 六、重點結論

1. **效能表現**：ODBC Bridge 結合顯式 DDL 代理表，同步速度達到 JDBC 的 **2.7 倍**，Airbyte 的 **21 倍**。
2. **儲存成本**：相較於 Airbyte 的龐大 metadata，ODBC/JDBC 皆無多餘空間損耗。
3. **穩定性**：ODBC Bridge 規避了 JDBC 與 Airbyte 可能遭遇的 Memory 與 GC 開銷瓶頸。

---

## 七、最終架構建議

###  建議採用「ODBC Bridge 專案客製方案」

考量本專案 LOB 鎖死問題與龐大資料量，最終放棄 Airbyte 與 JDBC 混合架構，全面採用以 Python 控制流輔助的 **ODBC Bridge (sync_unified_odbc.py)** 方案：
*   **單一技術棧**：統一以 ODBC 應付大、小表的同步，降低架構複雜度。
*   **最高效能**：平均 9 萬筆/秒的吞吐量，足可應付未來產線數據的線性成長。




