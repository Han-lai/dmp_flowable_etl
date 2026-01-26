-- ========================================
-- 資料庫初始化
-- ========================================

-- 建立資料庫（如果不存在）
CREATE DATABASE IF NOT EXISTS bronze;
CREATE DATABASE IF NOT EXISTS silver;
CREATE DATABASE IF NOT EXISTS gold;

-- 設定預設資料庫
USE bronze;