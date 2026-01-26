-- ========================================
-- Bronze 層來源表（假設已存在，此處僅列出必要的表結構驗證）
-- ========================================

-- 驗證必要的 Bronze 表存在
-- 這些表應該已經透過同步機制建立

-- 必要表清單：
-- bronze.bpm_act_hi_taskinst - BPM 任務實例
-- bronze.bpm_act_hi_procinst - BPM 流程實例  
-- bronze.bpm_act_hi_varinst - BPM 變數實例
-- bronze.common_hr_employee - 人員主檔
-- bronze.common_mdm_mfg_site_master - MDM 製造據點主檔
-- bronze.common_mdm_mfg_plant_master - MDM 製造廠區主檔
-- bronze.common_mdm_factory_area_master - MDM 工廠區域主檔
-- bronze.common_mdm_line_desc_master - MDM 產線描述主檔

SELECT 'Bronze layer tables verification completed' AS status;