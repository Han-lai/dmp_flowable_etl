-- ========================================
-- 步驟 0: 資料庫初始化
-- 用途: 確保 Bronze/Silver/Gold 資料庫存在
-- ========================================

CREATE DATABASE IF NOT EXISTS bronze;
CREATE DATABASE IF NOT EXISTS silver;
CREATE DATABASE IF NOT EXISTS gold;

SELECT name FROM system.databases WHERE name IN ('bronze', 'silver', 'gold');
