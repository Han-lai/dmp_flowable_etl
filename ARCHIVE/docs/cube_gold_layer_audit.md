# Cube.js Model Gold 層判定審查報告（修正後）

**審查日期：** 2026-01-12  
**審查範圍：** 3 個 Cube Model，19 個 Measures（修正後）

---

## 一、總覽結論

**Cube.js Model 整體屬於：**

☑ **混合狀態（Semantic Gold + Silver 包裝）**

**理由：**
1. 已移除 `SELECT *`，改為明確欄位選取
2. 7 個核心指標已具備 Gold 特性（語意完整、使用約束、聚合警告）
3. 12 個輔助指標標記為 Silver 包裝（internal）
4. 已建立治理文件 `docs/semantic_gold_governance.md`

**比例分析：**
- 🥇 Gold 指標：7 個 (37%)
- 🥈 Silver 包裝：12 個 (63%)

---

## 二、指標逐一鑑定表（修正後）

### 2.1 ProcTaskNode (任務節點)

| 指標名稱 | 來源 | Gold 判定 | 關鍵理由 |
|---------|------|----------|----------|
| `inProgressTaskCount` | RMV_HI_PROC_TASK_NODE | ✅ Gold | 語意完整、有維度約束、有使用說明 |
| `autoCompleteRate` | RMV_HI_PROC_TASK_NODE | ✅ Gold | 語意完整、有聚合警告、提供分子分母 |
| `avgWorkDuration` | RMV_HI_PROC_TASK_NODE | ✅ Gold | 語意完整、有聚合警告、提供 sum+count |
| `todoCount` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 標記 internal，供前端組合使用 |
| `doingCount` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 同上 |
| `doneCount` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 同上 |
| `doneAutoCount` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 同上 |
| `cancelledCount` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 同上 |
| `doneAutoForRate` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 輔助指標，供跨維度重算 |
| `doneTotalForRate` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 同上 |
| `totalWorkDuration` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 同上 |
| `avgIdleDuration` | RMV_HI_PROC_TASK_NODE | 🥈 Silver | 輔助指標 |

### 2.2 ProcInstNode (流程實例)

| 指標名稱 | 來源 | Gold 判定 | 關鍵理由 |
|---------|------|----------|----------|
| `inProgressCount` | RMV_HI_PROCINST_NODE | ✅ Gold | 語意完整、有維度約束 |
| `completedCount` | RMV_HI_PROCINST_NODE | ✅ Gold | 語意完整、有維度約束 |
| `mainProcCount` | RMV_HI_PROCINST_NODE | 🥈 Silver | 標記 internal |
| `subProcCount` | RMV_HI_PROCINST_NODE | 🥈 Silver | 同上 |
| `avgDuration` | RMV_HI_PROCINST_NODE | 🥈 Silver | 有聚合警告，提供 sum+count |
| `totalDuration` | RMV_HI_PROCINST_NODE | 🥈 Silver | 輔助指標 |

### 2.3 BizEventInfo (業務事件)

| 指標名稱 | 來源 | Gold 判定 | 關鍵理由 |
|---------|------|----------|----------|
| `inProgressEventCount` | RMV_HI_BIZ_EVENT_INFO | ✅ Gold | 語意完整、有維度約束、有限制說明 |
| `avgTotalDuration` | RMV_HI_BIZ_EVENT_INFO | ✅ Gold | 語意完整、有聚合警告、提供 sum+count |
| `completedEventCount` | RMV_HI_BIZ_EVENT_INFO | 🥈 Silver | 輔助指標，供跨維度重算 |
| `totalDurationSum` | RMV_HI_BIZ_EVENT_INFO | 🥈 Silver | 同上 |

---

## 三、Gold 判定面向詳細分析（修正後）

### 3.1 指標語意完整性

| 面向 | 判定 | 說明 |
|------|------|------|
| 能用一句業務語言描述 | ✅ 是 | 所有 Gold 指標都有完整 description |
| 不依賴查詢者理解 | ✅ 是 | description 包含合法/禁止維度說明 |

### 3.2 指標定義穩定性

| 面向 | 判定 | 說明 |
|------|------|------|
| 不因多 join 改變數值 | ✅ 是 | 來源是已聚合的 RMV，無 join 風險 |
| 避免 row multiplication | ✅ 是 | 每個 Cube 有明確 Grain |

### 3.3 使用方式約束

| 面向 | 判定 | 說明 |
|------|------|------|
| 限制可用 dimensions | ✅ 是 | description 標註合法/禁止維度 |
| 限制 time dimension | ✅ 是 | description 標註適用時間維度與粒度 |

### 3.4 跨系統共用性

| 面向 | 判定 | 說明 |
|------|------|------|
| 適合多 dashboard 共用 | ✅ 是 | 有使用規範文件 |
| 可作為 KPI/SLA 指標 | ⚠️ 部分 | 需建立版本控制 |

### 3.5 官方定義特性

| 面向 | 判定 | 說明 |
|------|------|------|
| Single Source of Truth | ✅ 是 | 已移除重複指標，每個指標只在單一 Cube |
| 清楚命名與說明 | ✅ 是 | 有 🥇/🥈 標記區分層級 |

---

## 四、架構層級建議（修正後）

### 4.1 已達成 Semantic Gold 的指標（7 個）

| 指標 | Cube | 狀態 |
|------|------|------|
| `inProgressTaskCount` | ProcTaskNode | ✅ Semantic Gold |
| `autoCompleteRate` | ProcTaskNode | ✅ Semantic Gold |
| `avgWorkDuration` | ProcTaskNode | ✅ Semantic Gold |
| `inProgressCount` | ProcInstNode | ✅ Semantic Gold |
| `completedCount` | ProcInstNode | ✅ Semantic Gold |
| `inProgressEventCount` | BizEventInfo | ✅ Semantic Gold |
| `avgTotalDuration` | BizEventInfo | ✅ Semantic Gold |

### 4.2 維持在 Silver 包裝的指標（12 個）

| 指標 | Cube | 用途 |
|------|------|------|
| `todoCount`, `doingCount`, `doneCount`, `doneAutoCount`, `cancelledCount` | ProcTaskNode | 狀態分布組件 |
| `doneAutoForRate`, `doneTotalForRate`, `totalWorkDuration` | ProcTaskNode | 跨維度重算輔助 |
| `avgIdleDuration` | ProcTaskNode | 輔助分析 |
| `mainProcCount`, `subProcCount`, `avgDuration`, `totalDuration` | ProcInstNode | 輔助分析 |
| `completedEventCount`, `totalDurationSum` | BizEventInfo | 跨維度重算輔助 |

### 4.3 已移除的指標

| 指標 | 原 Cube | 移除原因 |
|------|---------|----------|
| `count` | 所有 Cube | 無業務語意 |
| `inProgressTaskCount` | BizEventInfo | 與 ProcTaskNode 重複 |
| `totalTaskCount`, `todoTaskCount`, `doingTaskCount` | BizEventInfo | 與 ProcTaskNode 重複 |
| `processCount` | BizEventInfo | 技術指標 |

---

## 五、結論（修正後）

**修正前狀態：** Silver 包裝層（0% Gold）
**修正後狀態：** 混合狀態（37% Gold + 63% Silver 包裝）

**已完成的改進：**
1. ✅ 移除 `SELECT *`，改為明確欄位選取
2. ✅ 為 Gold 指標加上維度約束說明
3. ✅ 移除重複指標，確保 Single Source of Truth
4. ✅ 為 avg/rate 指標加上聚合警告，提供分子分母
5. ✅ 建立治理文件 `docs/semantic_gold_governance.md`

**相關文件：**
- `docs/semantic_gold_governance.md` - 指標治理文件
- `docs/metrics_in_cubejs.md` - 指標應用手冊

---

**文件結束**
