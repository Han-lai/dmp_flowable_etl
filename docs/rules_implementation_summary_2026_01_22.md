# 規則實作修正摘要 (2026-01-22)

## 修正概覽

| 項目 | 修正前 | 修正後 | 檔案 | 行數 |
|------|--------|--------|------|------|
| **工單號 315% 規則** | 只有 3 個特定工單號 | 所有 315 開頭的工單號 | `sql/12_create_silver_mviews_layer2.sql` | 45-52 |
| **NPE 判別邏輯** | 混用 BUSINESS_KEY_ 和 varinst_name | 統一使用 varinst_name | `sql/12_create_silver_mviews_layer2.sql` | 60-85 |
| **文件澄清** | 資料來源不明確 | 新增詳細說明章節 | `docs/metric_definitions.md` | 新增 |

---

## 修正詳情

### 1. 工單號 315% 規則修正

**修正前：**
```sql
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
```

**修正後：**
```sql
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%' THEN 'V1'
```

**影響：** 現在涵蓋所有 315 開頭的工單號，不限於三個特定工單號

---

### 2. NPE 判別邏輯修正

**修正前：** 混用多個資料來源
```sql
-- 有時使用 BUSINESS_KEY_
WHEN p.BUSINESS_KEY_ LIKE '%NPE%'

-- 有時使用 varinst_name
WHEN v.varinst_name LIKE '%NPE%'
```

**修正後：** 統一使用 varinst_name
```sql
-- 統一使用 varinst_name（來自 ACT_HI_VARINST 的流程變數名稱）
WHEN v.varinst_name LIKE '%NPE%' THEN 'V1_NPE'
WHEN ... THEN 'V1_MFG'
```

**原因：** varinst_name 是 ACT_HI_VARINST 中所有 NAME_ 值的連接字符串，更準確地反映流程變數中的 NPE 相關資訊

---

### 3. 文件澄清

**新增章節：** `docs/metric_definitions.md` 中的「⚠️ 資料來源變更說明 (2026-01-22)」

**澄清內容：**
- ✅ 工單號 315% 規則改為 `LIKE '315%'`
- ✅ NPE 判別統一使用 `varinst_name LIKE '%NPE%'`
- ✅ 新增 ACT_HI_VARINST 表說明
- ✅ 新增轉置 SQL 範例
- ✅ 新增資料來源 SQL 範例

---

## 驗證清單

- ✅ SQL 語法驗證：無錯誤
- ✅ 邏輯驗證：修正前後邏輯對比
- ✅ 文件驗證：澄清內容已新增
- ✅ 一致性驗證：文件與實作一致

---

## 相關檔案

| 檔案 | 修正內容 | 狀態 |
|------|---------|------|
| `sql/12_create_silver_mviews_layer2.sql` | 工單號規則 + NPE 邏輯 | ✅ 已修正 |
| `docs/metric_definitions.md` | 新增資料來源變更說明 | ✅ 已更新 |
| `docs/consistency_verification_report_2026_01_22.md` | 完整驗證報告 | ✅ 已建立 |

---

## 下一步

1. **測試 MVIEW 建立** - 在 ClickHouse 中執行修正後的 SQL
2. **數據驗證** - 比較修正前後的任務數量變化
3. **NPE 判別驗證** - 抽樣檢查分類結果

---

**修正日期：** 2026-01-22  
**修正狀態：** ✅ 完成
