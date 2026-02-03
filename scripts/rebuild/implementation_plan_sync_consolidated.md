# Consolidate Batch Sync Script Implementation Plan

## Goal
Create a single Python script `scripts/rebuild/sync_batches_consolidated.py` to sync the following tables from MSSQL to ClickHouse using batch processing (except PROCDEF which is small):
1. `APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108`
2. `APP_SRV_BPM.dbo.ACT_HI_VARINST_0108`
3. `APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108`
4. `APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0108`

## Key Requirements
1. **Source**: MSSQL (`WJOAUATDB01S.delta.corp:65000`)
2. **Target**: ClickHouse (`bronze` layer)
3. **Method**: JDBC Bridge (`jdbc('mssql_master', ...)`)
4. **Strategy**: 
    - **Large Tables** (TASKINST, VARINST, PROCINST): Batch sync by time range (e.g., monthly/daily chunks).
    - **Small Tables** (PROCDEF): Full sync.
5. **Safety**: Incorporate strict deletion rules (ask user confirmation if needed, though this is a sync script so it implies data replacement/insertion).

## Proposed Script Structure
- **Configuration**: Define table mappings, source/target tables, time columns for batching.
- **Batch Generator**: Function to generate time ranges (e.g., `2023-01-01` to `Now`, step 30 days).
- **Executors**:
    - `sync_large_table_batches(table_config)`: Iterates through time ranges, clears target data for that range (if retry), and inserts data.
    - `sync_small_table_full(table_config)`: Truncates and reloads entire table.
- **CLI Args**: Allow users to specify which table to sync (e.g., `--table taskinst` or `--all`) and date range (`--start`, `--end`).

## Table Specifics
| Table | Source | Time Column (for batching) | Strategy |
| :--- | :--- | :--- | :--- |
| **TASKINST** | `ACT_HI_TASKINST_0108` | `START_TIME_` | Batch (Monthly) |
| **VARINST** | `ACT_HI_VARINST_0108` | `CREATE_TIME_` | Batch (Monthly) |
| **PROCINST** | `ACT_HI_PROCINST_0108` | `START_TIME_` | Batch (Monthly) |
| **PROCDEF** | `ACT_RE_PROCDEF_0108` | N/A | Full Sync |

## Validation Plan
- Dry-Run mode to list batches without executing.
- Count validation after sync.
