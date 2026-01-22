# Implementation Plan: Fix 315% Work Order Rule Consistency

## Overview

修正系統中 315% 工單號歸屬規則的不一致問題，將所有使用特定工單號列表的地方改為使用 `LIKE '315%'` 模式匹配，確保所有 315 開頭的工單號都正確歸類為 V1 任務。

## Tasks

- [x] 1. 修正對帳驗證腳本中的 315% 規則
  - 更新 `scripts/verify_mssql_clickhouse_reconciliation.py` 中的 V1 歸屬邏輯
  - 更新 `scripts/debug_mssql_v3_tasks.py` 中的歸屬邏輯
  - 更新 `scripts/debug_mssql_date_logic.py` 中的歸屬邏輯
  - _Requirements: 2.1, 2.3_
  - **Status**: ❌ Still using hardcoded `IN ('3152600035', '3152600036', '3152600037')` pattern

- [ ]* 1.1 Write property test for cross-system consistency
  - **Property 2: Cross-System Classification Consistency**
  - **Validates: Requirements 2.2, 4.2**

- [x] 2. 修正轉換腳本中的 315% 規則
  - 更新 `scripts/transform_silver_generic_metrics.py` 中的工單號規則
  - 確保 V1 歸屬邏輯使用 `LIKE '315%'` 模式
  - 更新 V1_NPE 和 V1_MFG 子類型邏輯
  - _Requirements: 1.1, 1.4_
  - **Status**: ❌ Still using hardcoded `IN ('3152600035', '3152600036', '3152600037')` pattern

- [ ]* 2.1 Write property test for universal 315% classification
  - **Property 1: Universal 315% Work Order Classification**
  - **Validates: Requirements 1.1, 1.4**

- [x] 3. 更新文檔和報告
  - 修正 `scripts/final_reconciliation_report.py` 中的說明文字
  - 更新 `docs/metric_definitions.md` 中的 315% 規則說明
  - 更新 `docs/vx_attribution_logic_correction.md` 中的範例
  - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - **Status**: ✅ Documentation already updated with correct `LIKE '315%'` pattern

- [ ]* 3.1 Write unit tests for documentation updates
  - Test that documentation contains correct `LIKE '315%'` references
  - Test that old hardcoded work order numbers are removed from docs
  - _Requirements: 3.1, 3.2_

- [x] 4. 修正 SQL 檔案中的規則
  - 更新 `sql/fix_v1_v3_attribution_logic.sql` 中的邏輯
  - 確保所有 SQL 查詢使用一致的 315% 規則
  - _Requirements: 1.3, 4.1_
  - **Status**: ✅ SQL files already use correct `LIKE '315%'` pattern

- [ ]* 4.1 Write unit tests for SQL pattern verification
  - Test that SQL files contain `LIKE '315%'` patterns
  - Test that hardcoded work order lists are removed
  - _Requirements: 1.3, 2.3_

- [x] 5. Fix remaining hardcoded patterns in reconciliation scripts
  - Update `scripts/verify_mssql_clickhouse_reconciliation.py` to use `LIKE '315%'`
  - Update `scripts/debug_mssql_v3_tasks.py` to use `LIKE '315%'` 
  - Update `scripts/debug_mssql_date_logic.py` to use `LIKE '315%'`
  - _Requirements: 2.1, 2.3_

- [x] 6. Fix hardcoded pattern in transform script
  - Update `scripts/transform_silver_generic_metrics.py` to use `LIKE '315%'`
  - Update V1_NPE and V1_MFG subtype logic to use `LIKE '315%'`
  - _Requirements: 1.1, 1.4_

- [x] 7. Checkpoint - 驗證規則一致性
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. 建立系統一致性驗證工具
  - 創建腳本掃描所有檔案中的 315% 規則實作
  - 識別任何剩餘的硬編碼工單號參考
  - 驗證所有組件使用相同的模式
  - _Requirements: 4.1, 4.3_

- [ ]* 8.1 Write property test for system-wide consistency
  - **Property 3: System-Wide Rule Consistency**
  - **Validates: Requirements 4.1, 4.4**

- [ ] 9. 執行端到端測試
  - 使用 315% 工單號測試完整的資料流程
  - 驗證 Bronze → Silver → Gold 層的一致性
  - 確認對帳結果正確反映修正後的規則
  - _Requirements: 4.4_

- [ ]* 9.1 Write integration tests for end-to-end validation
  - Test complete data pipeline with 315% work orders
  - Test reconciliation accuracy with corrected rules
  - _Requirements: 4.4_

- [ ] 10. Final checkpoint - 確認所有測試通過
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Focus on changing hardcoded `IN ('3152600035', '3152600036', '3152600037')` to `LIKE '315%'`
- Ensure all 315% work orders are classified as V1, not just the three specific ones