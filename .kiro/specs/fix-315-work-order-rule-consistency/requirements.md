# Requirements Document

## Introduction

修正 V1/V3 歸屬邏輯中 315% 工單號規則的不一致問題。目前系統中部分檔案使用正確的 `LIKE '315%'` 規則，但關鍵的對帳驗證腳本仍使用錯誤的特定工單號規則。

## Glossary

- **System**: DMP Flowable 流程分析系統
- **Work_Order_Rule**: 工單號歸屬規則
- **V1_Attribution**: V1 任務歸屬邏輯
- **Reconciliation_Scripts**: 對帳驗證腳本

## Requirements

### Requirement 1: 統一 315% 工單號規則

**User Story:** As a system administrator, I want all 315% work orders to be classified as V1 tasks, so that the business rule is consistently applied across all system components.

#### Acceptance Criteria

1. WHEN the system processes any work order starting with "315", THE System SHALL classify it as V1 task
2. WHEN the system encounters work orders like "3152600035", "3152600036", "3152600037", "3152600038", "3152600100", THE System SHALL classify all of them as V1 tasks
3. THE System SHALL use `LIKE '315%'` pattern matching instead of specific work order number lists
4. WHEN processing V1 attribution logic, THE System SHALL apply 315% rule consistently across all components

### Requirement 2: 修正對帳驗證腳本

**User Story:** As a data analyst, I want reconciliation scripts to use the correct 315% work order rule, so that MSSQL and ClickHouse comparisons are accurate.

#### Acceptance Criteria

1. WHEN reconciliation scripts check V1/V3 attribution, THE System SHALL use `LIKE '315%'` pattern
2. WHEN comparing MSSQL and ClickHouse data, THE System SHALL apply identical 315% work order rules
3. THE System SHALL remove hardcoded work order numbers ('3152600035', '3152600036', '3152600037') from reconciliation logic
4. WHEN generating reconciliation reports, THE System SHALL reflect the corrected 315% rule implementation

### Requirement 3: 更新相關文檔

**User Story:** As a developer, I want documentation to reflect the correct 315% work order rule, so that future implementations follow the right pattern.

#### Acceptance Criteria

1. WHEN developers reference metric definitions, THE System SHALL document `LIKE '315%'` as the standard rule
2. WHEN reviewing reconciliation reports, THE System SHALL explain that all 315% work orders are classified as V1
3. THE System SHALL update error messages and comments to reflect the correct rule
4. WHEN troubleshooting attribution logic, THE System SHALL provide accurate rule descriptions

### Requirement 4: 驗證規則一致性

**User Story:** As a quality assurance engineer, I want to verify that all system components use the same 315% work order rule, so that data consistency is maintained.

#### Acceptance Criteria

1. WHEN running system validation, THE System SHALL confirm all components use `LIKE '315%'` pattern
2. WHEN checking different data layers (Bronze, Silver, Gold), THE System SHALL apply consistent 315% rules
3. THE System SHALL identify any remaining hardcoded work order number references
4. WHEN performing end-to-end testing, THE System SHALL validate 315% work order classification consistency