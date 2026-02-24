
import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

ddl_config = """
CREATE TABLE IF NOT EXISTS bronze.common_dmp_function_config
(
    `ID` Int64,
    `Plant` Nullable(String),
    `Creator` Nullable(String),
    `Factory` Nullable(String),
    `Updater` Nullable(String),
    `LineName` Nullable(String),
    `UpdateCount` Nullable(Int64),
    `FunctionCode` Nullable(String),
    `AssignLineFlag` Nullable(String),
    `CreateDatetime` Nullable(DateTime64(3)),
    `ProductionArea` Nullable(String),
    `UpdateDatetime` Nullable(DateTime64(3)),
    `SyncESB` Nullable(String),
    `StartDps` Nullable(String),
    `AssignWorkStatus` Nullable(String),
    `EffectiveEndDate` Nullable(DateTime64(3)),
    `EffectiveStartDate` Nullable(DateTime64(3)),
    `_batch_id` String,
    `_extracted_at` DateTime64(3),
    `_sync_version` UInt64
)
ENGINE = ReplacingMergeTree(_extracted_at)
ORDER BY (ID)
SETTINGS index_granularity = 8192
"""

ddl_mapping = """
CREATE TABLE IF NOT EXISTS bronze.common_dmp_function_client_mapping
(
    `ID` Int64,
    `Plant` Nullable(String),
    `Logsys` Nullable(String),
    `Region` Nullable(String),
    `Creator` Nullable(String),
    `Updater` Nullable(String),
    `UpdateCount` Nullable(Int64),
    `CreateDatetime` Nullable(DateTime64(3)),
    `UpdateDatetime` Nullable(DateTime64(3)),
    `_batch_id` String,
    `_extracted_at` DateTime64(3),
    `_sync_version` UInt64
)
ENGINE = ReplacingMergeTree(_extracted_at)
ORDER BY (ID)
SETTINGS index_granularity = 8192
"""

try:
    print("Creating bronze.common_dmp_function_config...")
    client.command(ddl_config)
    print("Success.")
except Exception as e:
    print(f"Error creating config table: {e}")

try:
    print("Creating bronze.common_dmp_function_client_mapping...")
    client.command(ddl_mapping)
    print("Success.")
except Exception as e:
    print(f"Error creating mapping table: {e}")
