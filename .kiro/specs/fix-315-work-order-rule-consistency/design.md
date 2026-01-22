# Design Document

## Overview

This design addresses the inconsistency in 315% work order classification rules across the DMP Flowable system. Currently, some components use the correct `LIKE '315%'` pattern while critical reconciliation scripts still use hardcoded specific work order numbers. This creates data inconsistency and incorrect reconciliation results.

## Architecture

The fix involves updating multiple layers of the system:

1. **Reconciliation Layer**: Update verification and comparison scripts
2. **Documentation Layer**: Correct metric definitions and reports
3. **Validation Layer**: Ensure consistency checks use correct rules

## Components and Interfaces

### 1. Reconciliation Scripts
- `scripts/verify_mssql_clickhouse_reconciliation.py`
- `scripts/debug_mssql_v3_tasks.py`
- `scripts/final_reconciliation_report.py`
- `scripts/debug_mssql_date_logic.py`

### 2. Transformation Scripts
- `scripts/transform_silver_generic_metrics.py`

### 3. Documentation Files
- `docs/metric_definitions.md`
- `docs/vx_attribution_logic_correction.md`

### 4. SQL Files
- `sql/fix_v1_v3_attribution_logic.sql`

## Data Models

### Current Incorrect Pattern
```sql
WHEN COALESCE(v.varinst_moNumber, '') IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
```

### Correct Pattern
```sql
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%' THEN 'V1'
```

### V1 Attribution Logic (Corrected)
```sql
CASE 
    -- Priority 1: Work order rules (highest priority)
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%'
    THEN 'V1'
    -- Priority 2: TaskDefinitionKey
    WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
    WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
    ELSE COALESCE(substring(t.TaskDefinitionKey, 1, 2), 'Unknown')
END
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After reviewing the prework analysis, several properties can be consolidated:
- Properties 1.1 and 1.4 both test universal 315% classification - can be combined
- Properties 2.2 and 4.2 both test consistency across systems/layers - can be combined  
- Properties 4.1 and 4.4 both test system-wide validation - can be combined

### Core Properties

**Property 1: Universal 315% Work Order Classification**
*For any* work order number starting with "315", the system should classify it as V1 task regardless of the original TaskDefinitionKey
**Validates: Requirements 1.1, 1.4**

**Property 2: Cross-System Classification Consistency**
*For any* 315% work order, MSSQL and ClickHouse systems should produce identical V1 classification results
**Validates: Requirements 2.2, 4.2**

**Property 3: System-Wide Rule Consistency**
*For any* system component processing 315% work orders, the classification logic should use `LIKE '315%'` pattern and produce consistent results
**Validates: Requirements 4.1, 4.4**

<function_calls>
<invoke name="prework">
<parameter name="featureName">fix-315-work-order-rule-consistency

## Error Handling

### Invalid Work Order Numbers
- Handle NULL or empty work order numbers gracefully
- Log warnings for unexpected work order formats
- Default to TaskDefinitionKey-based classification when work order is invalid

### Pattern Matching Failures
- Ensure LIKE pattern matching handles edge cases
- Validate that pattern matching is case-insensitive where appropriate
- Handle special characters in work order numbers

### Cross-System Inconsistencies
- Detect and report when MSSQL and ClickHouse produce different results
- Provide detailed error messages for reconciliation failures
- Log specific work orders that cause classification discrepancies

## Testing Strategy

### Unit Tests
- Test specific examples of 315% work orders (3152600035, 3152600036, etc.)
- Verify code contains correct `LIKE '315%'` patterns
- Confirm removal of hardcoded work order lists
- Validate documentation updates

### Property-Based Tests
- **Property 1**: Generate random work orders starting with "315" and verify V1 classification
- **Property 2**: Test same work orders across MSSQL and ClickHouse for consistency
- **Property 3**: Validate all system components use consistent 315% rules

### Integration Tests
- End-to-end testing of reconciliation scripts with 315% work orders
- Cross-layer validation (Bronze → Silver → Gold) for classification consistency
- Verification that reports reflect correct rule implementation

### Configuration
- Minimum 100 iterations per property test
- Each property test tagged with: **Feature: fix-315-work-order-rule-consistency, Property {number}: {property_text}**
- Both unit and property tests are required for comprehensive coverage