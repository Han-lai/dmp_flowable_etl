# MSSQL 來源表 vs sync_unified.py 配置對比分析

## 📋 MSSQL 來源表清單 (23 張)

### APP_SRV_COMMON.dbo 表
1. DMPFunctionClientMapping_0202
2. DMPFunctionConfig_0202
3. EmpNodeRoleMapping_0202
4. EmpOrgInfoMapping_0202
5. EmpUserGroupMapping_0202
6. FlowableTaskStats_0202 (重複)
7. HR_Employee_0202
8. MDM_BG_ORG_TYPE_MASTER_0202
9. MDM_BU_ORG_TYPE_MASTER_0202
10. MDM_DEPT_ORG_TYPE_MASTER_0202
11. MDM_FACTORY_AREA_MASTER_0202
12. MDM_FOM_JOB_0202
13. MDM_LINE_DESC_MASTER_0202
14. MDM_MFG_PLANT_MASTER_0202
15. MDM_MFG_SITE_MASTER_0202
16. MDM_ORG_AREA_0202
17. MDM_ORG_PROFILE_MASTER_0202
18. MDM_PROD_AREA_MASTER_0202
19. ProcessRoleGroupMapping_0202
20. ProcessRoleGroup_0202
21. ProcessRoleUserMapping_0202
22. UserGroup_0202

## ✅ 已配置在 sync_unified.py 的表 (11 張)

### HR & Common 表
- EmpNodeRoleMapping_0202 → `common_emp_node_role_mapping` ✅
- EmpOrgInfoMapping_0202 → `common_emp_org_info_mapping` ✅
- EmpUserGroupMapping_0202 → `common_emp_user_group_mapping` ✅
- HR_Employee_0202 → `common_hr_employee` ✅ (但配置中寫的是 HREmployee，需確認)
- ProcessRoleUserMapping_0202 → `common_process_role_user_mapping` ✅
- UserGroup_0202 → `common_user_group` ✅


### DMP 功能配置表 (用於 L7 指標計算)
- DMPFunctionConfig_0202 → `bronze.common_dmp_function_config` ✅
- DMPFunctionClientMapping_0202 → `bronze.common_dmp_function_client_mapping` ✅

### MDM 主檔表
- MDM_LINE_DESC_MASTER_0202 → `common_mdm_line_desc_master` ✅
- MDM_PROD_AREA_MASTER_0202 → `common_mdm_prod_area_master` ✅
- MDM_FACTORY_AREA_MASTER_0202 → `common_mdm_factory_area_master` ✅
- MDM_MFG_SITE_MASTER_0202 → `common_mdm_mfg_site_master` ✅
- MDM_MFG_PLANT_MASTER_0202 → `common_mdm_mfg_plant_master` ✅

## ❌ 缺少的表 (9 張)

### MDM 組織主檔表 (6 張)
3. **MDM_BG_ORG_TYPE_MASTER_0202** - BG 組織類型主檔
4. **MDM_BU_ORG_TYPE_MASTER_0202** - BU 組織類型主檔
5. **MDM_DEPT_ORG_TYPE_MASTER_0202** - 部門組織類型主檔
6. **MDM_FOM_JOB_0202** - FOM 工作主檔
7. **MDM_ORG_AREA_0202** - 組織區域
8. **MDM_ORG_PROFILE_MASTER_0202** - 組織檔案主檔

### 流程角色群組表 (2 張)
9. **ProcessRoleGroup_0202** - 流程角色群組
10. **ProcessRoleGroupMapping_0202** - 流程角色群組對應

### 統計表 (1 張)
11. **FlowableTaskStats_0202** - Flowable 任務統計表

## 📊 統計摘要

- **MSSQL 來源表總數**: 22 張 (去重後)
- **已配置**: 13 張 (59%)
- **缺少**: 9 張 (41%)

## 💡 建議

### 優先級 1 (核心業務)
- `FlowableTaskStats_0202` - 如果需要使用預聚合統計表

### 優先級 2 (組織維度補齊)
- `MDM_BG_ORG_TYPE_MASTER_0202`
- `MDM_BU_ORG_TYPE_MASTER_0202`
- `MDM_DEPT_ORG_TYPE_MASTER_0202`
- `MDM_ORG_PROFILE_MASTER_0202`

### 優先級 3 (角色管理)
- `ProcessRoleGroup_0202`
- `ProcessRoleGroupMapping_0202`

