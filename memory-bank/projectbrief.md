# 專案概述 - DMP Flowable

## 專案名稱
DMP Flowable 資料同步專案

## 目標
將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver/Gold 層資料倉儲，並透過 Cube.js 提供 API。

## 核心功能
1. **資料同步**: MSSQL → ClickHouse (18 張表，5 大表增量 + 13 小表全量)
2. **資料轉換**: Bronze → Silver → Gold 三層架構
3. **指標計算**: L5 任務完成率、人員使用率等
4. **API 服務**: Cube.js 語意層 API

## 專案狀態
🟢 **已完成** - Bronze/Silver/Gold/Cube.js 全部到位

## 維護者
- 使用 ClickHouse 24.x
- 使用 Cube.js 作為語意層
- 使用 Airflow 進行排程管理
