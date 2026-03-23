-- -- ========================================
-- -- 步驟 5: Silver Layer - Dim Users (Config)
-- -- 內容: dim_config_users (分母定義)
-- -- 前置: 02_bronze_common_dims, 03_silver_pivot_and_hierarchy
-- -- ========================================

-- -- DROP TABLE IF EXISTS silver.dim_config_users;

-- CREATE VIEW silver.dim_config_users AS

-- WITH 
-- -- 1. User Logic (White/Blacklist by Name)
-- UserGroupsJoined AS (
--     SELECT 
--         m.EmpCode,
--         g.UserGroupName
--     FROM bronze.common_emp_user_group_mapping m
--     JOIN bronze.common_user_group g ON m.UserGroupId = g.UserGroupId
-- ),
-- UserGroupsCalculated AS (
--     SELECT EmpCode,
--            -- 排除名單: ManagerUser, LocalAdmin, GlobalAdmin, SystemAdmin, InternalAudit, SeniorOfficers&DTO
--            countIf(UserGroupName IN (
--                'ManagerUser', 
--                'LocalAdmin', 
--                'GlobalAdmin', 
--                'SystemAdmin', 
--                'InternalAudit', 
--                'SeniorOfficers&DTO'
--            )) > 0 as has_exclude,
           
--            -- V1 白名單: User, PMUser, PowerUser
--            countIf(UserGroupName IN ('User', 'PMUser', 'PowerUser')) > 0 as has_whitelist_v1,
           
--            -- V2/V3 嚴格名單: 只有 User
--            (countIf(UserGroupName = 'User') > 0 AND countIf(UserGroupName != 'User') = 0) as is_strict_user_v23
--     FROM UserGroupsJoined
--     GROUP BY EmpCode
-- ),

-- -- 2. Vx Logic (NodeCode) -> Explode to V1/V2/V3
-- UserVxRaw AS (
--     SELECT DISTINCT EmpCode, NodeCode
--     FROM bronze.common_emp_node_role_mapping
-- ),
-- UserVx AS (
--     SELECT EmpCode,
--            vx_type,
--            NodeCode
--     FROM UserVxRaw
--     ARRAY JOIN 
--         arrayFilter(x -> x != '', [
--             IF(NodeCode LIKE '%V1_%', 'V1', ''),
--             IF(NodeCode LIKE '%V2_%', 'V2', ''),
--             IF(NodeCode LIKE '%V3_%', 'V3', '')
--         ]) AS vx_type
-- ),

-- -- 3. Five Level Hierarchy (Factory Level Scope)
-- FactoryDim AS (
--     SELECT DISTINCT region_code, plant_code, factory_code
--     FROM silver.mv_dim_mfg_five_level
-- ),
-- OrgAssignments AS (
--     SELECT 
--         o.EmpCode,
--         COALESCE(fd.region_code, 'Unknown') as region_code,
--         o.Plant as plant_code,
--         o.MFGFactoryId as factory_code,
--         'ALL' as line_name -- Represents Factory Level Scope
--     FROM bronze.common_emp_org_info_mapping o
--     LEFT JOIN FactoryDim fd ON o.MFGFactoryId = fd.factory_code
-- ),

-- -- 4. Five Level Hierarchy (Line Level Scope)
-- LineAssignments AS (
--     SELECT 
--         p.EmpCode,
--         COALESCE(d.region_code, 'Unknown') as region_code,
--         p.Plant as plant_code,
--         p.Factory as factory_code,
--         p.LineName as line_name
--     FROM bronze.common_process_role_user_mapping p
--     LEFT JOIN silver.mv_dim_mfg_five_level d ON p.LineName = d.line_name
-- ),

-- -- 5. Combine Assignments
-- AllAssignments AS (
--     SELECT * FROM OrgAssignments
--     UNION DISTINCT
--     SELECT * FROM LineAssignments
-- ),

-- -- 6. Apply Filter & Logic
-- FilteredResult AS (
--     SELECT DISTINCT
--         -- NPE Check Logic: V3 + NPE -> V1
--         -- 判斷 Factory 或 Plant 是否包含 'NPE'
--         CASE 
--             WHEN uv.vx_type = 'V3' 
--                  AND (a.factory_code LIKE '%NPE%' OR a.plant_code LIKE '%NPE%') 
--             THEN 'V1'
--             ELSE uv.vx_type 
--         END AS final_vx_type,
        
--         a.region_code,
--         a.plant_code,
--         a.factory_code,
--         a.line_name,
--         a.EmpCode as emp_code
        
--     FROM AllAssignments a
--     JOIN UserVx uv ON a.EmpCode = uv.EmpCode
--     JOIN UserGroupsCalculated ug ON a.EmpCode = ug.EmpCode
    
--     WHERE 
--         -- Global Exclude
--         ug.has_exclude = 0
--         AND (
--             -- V1 Rule: Must be in Whitelist (User/PM/Power)
--             (uv.vx_type = 'V1' AND ug.has_whitelist_v1 = 1)
--             OR
--             -- V2/V3 Rule: Must be strictly User only
--             (uv.vx_type IN ('V2', 'V3') AND ug.is_strict_user_v23 = 1)
--         )
-- )

-- SELECT * FROM FilteredResult;

-- -- 驗證
-- SELECT 'silver.dim_config_users' as table_name, count() as row_count FROM silver.dim_config_users;
-- SELECT final_vx_type, count() FROM silver.dim_config_users GROUP BY final_vx_type;
