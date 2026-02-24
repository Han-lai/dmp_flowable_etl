# ClickHouse 專案文件索引 (Documentation Index)

本目錄包含 L5 指標與相關架構的核心文件，按建議閱讀順序排列：

## 🚀 核心開發文件
1.  **[01_Architecture_Overview.md](01_Architecture_Overview.md)**: 系統架構總覽、分層說明。
2.  **[01b_System_Flow_Diagram.md](01b_System_Flow_Diagram.md)**: 數據管道流向圖。
3.  **[02_E2E_Implementation_Guide.md](02_E2E_Implementation_Guide.md)**: **核心必讀**。開發、同步、驗證與故障排除指南。
4.  **[03_Business_Metric_Definitions.md](03_Business_Metric_Definitions.md)**: 業務指標 (L5/L7) 的精確定義。
5.  **[04_Data_Lineage_Mapping.md](04_Data_Lineage_Mapping.md)**: 五階維度與 MDM 來源血緣分析。
6.  **[05_Field_Verification_Reference.md](05_Field_Verification_Reference.md)**: MSSQL 與 ClickHouse 欄位對應與對帳手冊。
7.  **[03_1_columns_defin.md](03_1_columns_defin.md)**: 進階欄位細項定義與邏輯修正歷程。

## 🛠️ 技術細節
*   **[06_Technical_Deep_Dive_MViews.md](06_Technical_Deep_Dive_MViews.md)**: Silver 層 Materialized Views 的實作細節。

## 📋 業務規格與指南
*   **[specs/](specs/)** 目錄：
    *   [L5 Dashboard 規格書](specs/l5_dashboard_spec.md)
    *   [L7 人員使用率技術規格](specs/user_utilization_spec.md)

*   **[guides/](guides/)** 與本目錄手冊：
    *   [L5 專案完成度與 Superset 指南](L5_Completion_Superset_Guide.md)
    *   [L5 週期報表 V2 流程圖說明](L5_Periodic_Report_V2_Flow.md)
    *   [Superset 儀表板配置手冊](guides/superset_dashboard_guide.md)

## 📂 其他資源
*   **[reports/](reports/)**: 週期性報告紀錄。
*   **[refrence_sql/](refrence_sql/)**: 參考 SQL 與 DDL 快照。

---
> [!NOTE]
> 過去的調查報告位於 **[reports/](reports/)**，參考 SQL 位於 **[refrence_sql/](refrence_sql/)**。
