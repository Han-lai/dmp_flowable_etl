-- ========================================
-- 步驟 0: 資料庫初始化
-- 用途: 確保 Bronze/Silver/Gold/ops_metrics 資料庫存在
-- ========================================

CREATE DATABASE IF NOT EXISTS bronze;
CREATE DATABASE IF NOT EXISTS silver;
CREATE DATABASE IF NOT EXISTS gold;
CREATE DATABASE IF NOT EXISTS ops_metrics;

SELECT name FROM system.databases WHERE name IN ('bronze', 'silver', 'gold', 'ops_metrics');
