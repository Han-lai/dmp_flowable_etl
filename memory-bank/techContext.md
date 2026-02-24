# 技術環境 - DMP Flowable

## ClickHouse
- **Host**: REDACTED_IP
- **Port**: 8121
- **User**: default
- **Database**: bronze, silver, gold

## MSSQL
- **Host**: 10.136.218.192
- **Databases**: APP_SRV_BPM, APP_SRV_COMMON

## S3 (MinIO)
- **Bucket**: mfg-lakehouse
- **Office Access**: https://cnwjns3.deltaww.com/mfg-lakehouse/
- **Server Farm**: http://cnwjns3.delta.corp/mfg-lakehouse/

## Python 環境
- Python 3.10+
- Virtual env: `.venv/`
- 主要套件: clickhouse-connect, pymssql

## 重要路徑
| 路徑 | 說明 |
|------|------|
| `sql/etl/` | Bronze/Silver/Gold 層 SQL 定義 |
| `scripts/validation/` | 資料驗證腳本 |
| `docs/` | 文件與參考 SQL |
| `ARCHIVE/misc/CLAUDE.md` | 專案快速上手指南 |
