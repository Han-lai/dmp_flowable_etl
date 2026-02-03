# 人員使用率 (User Utilization) 實作缺失分析報告
**日期**: 2026-02-02
**狀態**: 🔴 嚴重缺失 (Critical Gaps Identified)

## 1. 核心定義落差

| 項目 | 文件定義 (Spec) | 目前實作 (Current) | 差異狀態 |
| :--- | :--- | :--- | :--- |
| **公式** | `Active Users / Config Users` | `Working Users / Active Users` | ❌ **完全錯誤** (分母定義嚴重偏離) |
| **Active Users** | 實際有操作的人 (Done/Doing) 且**在白名單內** | 僅檢查是否有操作任務 | ⚠️ 缺少白名單過濾 |
| **Config Users** | 具備系統操作權限的配置人數 | **N/A (未實作)** | 🔴 **完全缺失** |

## 2. 資料來源缺失 (Bronze Layer)

經檢查，計算 `Config Users` 所需的 5 張權限與組織表在 ClickHouse 中**不存在**：

*   `bronze.common_emp_node_role_mapping` (NodeCode 歸屬) ❌ **MISSING**
*   `bronze.common_emp_org_info_mapping` (Plant/Factory 歸屬) ❌ **MISSING**
*   `bronze.common_emp_user_group_mapping` (群組關聯) ❌ **MISSING**
*   `bronze.common_user_group` (群組白名單/黑名單) ❌ **MISSING**
*   `bronze.common_process_role_user_mapping` (Line 歸屬) ❌ **MISSING**

**影響**: 無法計算分母，導致使用率指標無法依據 Spec 實作。

## 3. 維度完整性缺失 (Manufacturing Levels)

製造五階 (Five Levels) 支援度不完整：

| 層級 | 需求 | 目前 Gold/Cube 支援 | 狀態 |
| :--- | :--- | :--- | :--- |
| **Region** | Required | ❌ 無 | 缺失 |
| **Vx** | Required | ✅ 有 | OK |
| **Plant** | Plant Code | ✅ 有 | OK |
| **Factory** | MFG_PLANT_CODES | ❌ 無 | 缺失 (需從 Org Info Mapping 取得) |
| **Line** | Line Name | ❌ 無 | 缺失 (需從 Process Role Mapping 取得) |

## 4. 建議修復路徑 (Rebuild Roadmap)

為符合文件定義，需執行以下工程：

1.  **Bronze 層補齊**:
    *   新增上述 5 張表的 ClickHouse 建表語句 (DDL)。
    *   設定 MSSQL -> ClickHouse 的同步機制 (ETL)。

2.  **Silver 層邏輯實作**:
    *   建立 `silver.dim_config_users`。
    *   實作複雜的 UserGroup 黑白名單過濾邏輯。
    *   實作 NodeCode -> Vx 轉換邏輯。
    *   實作 Factory / Line 的多對多歸屬展開邏輯。

3.  **Gold 層重構**:
    *   重寫 `gold.rmv_user_utilization`。
    *   加入 `Config Users` 計數 (Count Distinct)。
    *   補齊 Region / Factory / Line 維度欄位。

4.  **Cube 模型更新**:
    *   修正 `utilizationRate` 公式。
    *   新增缺失維度。
