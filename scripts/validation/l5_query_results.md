# L5 指標 SQL 查詢驗證結果

**執行時間:** 2026-02-02 09:17:52

**五階維度:** Region, Vx, Plant, Factory, Line

---

## 0. FlowableTaskStats 維度欄位檢查

### 可用維度欄位

| 欄位名稱 | 資料類型 |
|----------|----------|
| Plant | Nullable(String) |
| Factory | Nullable(String) |
| ProductionArea | Nullable(String) |
| Line | Nullable(String) |
| DeliveryArea | Nullable(String) |

### Plant 唯一值 (Top 10)

| Plant | 筆數 |
|-------|------|
| DG3 | 303,453 |
| DET6 | 63,116 |
| WJ2 | 21,592 |
| DG2 | 690 |
| WG1 | 198 |

### Factory 唯一值 (Top 10)

| Factory | 筆數 |
|---------|------|
| MULTI | 248,680 |
| FAKE | 37,323 |
| NBU | 14,944 |
| SV | 11,160 |
| SMT | 6,967 |
| NPE | 1,961 |
| FMBG_FAN | 1,189 |
| FAN2 | 815 |
| NW | 688 |
| IPS | 176 |

### Line 唯一值 (Top 10)

| Line | 筆數 |
|------|------|
| S01 | 39,122 |
| E4 | 6,162 |
| S05 | 3,555 |
| E5 | 3,239 |
| SMT-S26 | 1,604 |
| A01 | 1,020 |
| S12 | 562 |
| SMT-S27 | 471 |
| E1 | 455 |
| N25 | 391 |

---

## 查詢 1：基礎 L5 任務彙總 - 含五階維度 (單日 2025-12-25)

**篩選條件:** Plant=WJ2, Factory=NBU, Line=E5, Date=2025-12-25

| Region | Vx | Plant | Factory | Line | Total | TODO | DOING | DONE | 完成率 | 執行率 |
|--------|-----|-------|---------|------|------:|-----:|------:|-----:|-------:|-------:|
| CNE | V1 | WJ2 | NBU | E5 | 18 | 0 | 12 | 6 | 33.33% | 100.00% |

---

## 查詢 2：跨維度彙總 (不限定 Line，只看 WJ2 NBU)

**篩選條件:** Plant=WJ2, Factory=NBU, Date=2025-12-25

| Region | Vx | Plant | Factory | Line | Total | TODO | DOING | DONE | 完成率 |
|--------|-----|-------|---------|------|------:|-----:|------:|-----:|-------:|
| CNE | V1 | WJ2 | NBU | E4 | 5 | 0 | 0 | 5 | 100.00% |
| CNE | V1 | WJ2 | NBU | E5 | 18 | 0 | 12 | 6 | 33.33% |
| CNE | V1 | WJ2 | NBU | N29 | 1 | 0 | 1 | 0 | 0.00% |
| CNE | V1 | WJ2 | NBU | - | 41 | 0 | 0 | 41 | 100.00% |

---

## 查詢 3：按 Plant 層級彙總 (2025-12-25)

**篩選條件:** Date=2025-12-25 (不限 Plant)

| Region | Vx | Plant | Total | TODO | DOING | DONE | 完成率 |
|--------|-----|-------|------:|-----:|------:|-----:|-------:|
| CNE | V2 | DG3 | 8 | 0 | 0 | 8 | 100.00% |
| CNE | V1 | WJ2 | 83 | 0 | 13 | 70 | 84.34% |
| CNE | V2 | WJ2 | 23 | 0 | 0 | 23 | 100.00% |

---

## 查詢 4：按 Factory 層級彙總 (WJ2, 2025-12-25)

**篩選條件:** Plant=WJ2, Date=2025-12-25

| Region | Vx | Plant | Factory | Total | TODO | DOING | DONE | 完成率 |
|--------|-----|-------|---------|------:|-----:|------:|-----:|-------:|
| CNE | V1 | WJ2 | NBU | 65 | 0 | 13 | 52 | 80.00% |
| CNE | V1 | WJ2 | SMT | 12 | 0 | 0 | 12 | 100.00% |
| CNE | V1 | WJ2 | - | 6 | 0 | 0 | 6 | 100.00% |
| CNE | V2 | WJ2 | - | 23 | 0 | 0 | 23 | 100.00% |

---

## 查詢 5：完整五階維度任務明細 (樣本 20 筆)

**篩選條件:** Plant=WJ2, Factory=NBU, Line=E5, Date=2025-12-25

| Region | Vx | Plant | Factory | Line | TaskDefinitionKey | Status | MoNumber | Date |
|--------|-----|-------|---------|------|-------------------|--------|----------|------|
| CNE | V1 | WJ2 | NBU | E5 | V3_5_1_1_6 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_3_2 | DONE | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_1_1 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_1_1_7 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_1_3 | DONE | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_7_5 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_1_2_2 | DONE | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_4_2 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_1_1_11 | DONE | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_1_2 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_6_2 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_7_1 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_3_5 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_4_5 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_6_3 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_2_5_1 | DOING | 1991223001 | 2025-12-25 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_3_2_1 | DONE | 3152506743 | 2025-12-24 |
| CNE | V1 | WJ2 | NBU | E5 | V3_5_1_0_1 | DONE | 1991223001 | 2025-12-23 |

---

## 查詢 6：Region 欄位來源確認

> [!WARNING]
> FlowableTaskStats 表沒有 Region 欄位！

### 五階維度對應表

| 五階維度 | FlowableTaskStats 欄位 | 狀態 |
|----------|------------------------|------|
| Region | (無) | ❌ 需從 MDM 補齊 |
| Vx | TaskDefinitionKey (推導) | ✅ 可用 |
| Plant | Plant | ✅ 可用 |
| Factory | Factory | ✅ 可用 |
| Line | Line | ✅ 可用 |

### Region 補齊方式

1. 從 MDM 主檔 (`silver.dim_mfg_five_level`) 透過 Plant 串接取得 Region
2. 或直接使用硬編碼 (如 WJ2 → CNE)

---

## 查詢 7：月份彙總 (含五階維度, 2025-12 ~ 2026-01)

**篩選條件:** Plant=WJ2, Factory=NBU, Line=E5

| Region | Vx | Plant | Factory | Line | Month | Total | TODO | DOING | DONE | 完成率 |
|--------|-----|-------|---------|------|-------|------:|-----:|------:|-----:|-------:|
| CNE | V1 | WJ2 | NBU | E5 | 202512 | 94 | 46 | 7 | 41 | 43.62% |
| CNE | V1 | WJ2 | NBU | E5 | 202601 | 700 | 368 | 173 | 159 | 22.71% |
| CNE | V3 | WJ2 | NBU | E5 | 202601 | 35 | 23 | 4 | 8 | 22.86% |

---

## 查詢 8：Gold 層最終驗證 (自動刷新 View)

**篩選條件:** snapshot_date=2025-12-25, Plant=WJ2, Factory=NBU, Line=E5

| Date | Vx | Region | Plant | Factory | Line | Total | TODO | DOING | DONE | 完成率 |
|------|-----|--------|-------|---------|------|------:|-----:|------:|-----:|-------:|
| 2025-12-25 | V1 | WJ | WJ2 | NBU | E5 | 192 | 0 | 0 | 192 | 100.0% |

---

## ✅ 查詢驗證結論

### 五階維度對應總結

- ✅ **可從 FlowableTaskStats 直接取得:** Vx (推導), Plant, Factory, Line
- ❌ **需從其他來源補齊:** Region (透過 MDM 主檔或硬編碼)

### 建議

1. 若需完整五階維度，應 JOIN `silver.dim_mfg_five_level` 取得 Region
2. 或建立 Plant → Region 的映射表
