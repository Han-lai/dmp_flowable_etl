-- ============================================
-- APP_SRV_COMMON - DMP 完整 Schema
-- ============================================

USE APP_SRV_COMMON;
GO

-- 1. FlowableTaskStats - 任務統計彙總 (39 欄)
CREATE TABLE FlowableTaskStats (
    Id NUMERIC(19,0) NOT NULL,
    ProcessInstanceId VARCHAR(64) NULL,
    ProcessDefinitionKey VARCHAR(50) NULL,
    ProcessDefinitionName NVARCHAR(255) NULL,
    ProcessTeam VARCHAR(50) NULL,
    Plant VARCHAR(50) NULL,
    Factory VARCHAR(50) NULL,
    ProductionArea VARCHAR(50) NULL,
    Line VARCHAR(50) NULL,
    ModelName VARCHAR(50) NULL,
    DeliveryArea VARCHAR(50) NULL,
    ScheduleNumber VARCHAR(50) NULL,
    MoNumber VARCHAR(50) NULL,
    SapPlant VARCHAR(50) NULL,
    SapProductGroup VARCHAR(50) NULL,
    Pallet VARCHAR(50) NULL,
    TransferNo VARCHAR(50) NULL,
    QBlockEventId VARCHAR(64) NULL,
    DefectSn VARCHAR(64) NULL,
    Time_ NVARCHAR(64) NULL,
    TaskId VARCHAR(64) NULL,
    TaskDefinitionKey VARCHAR(50) NULL,
    TaskName NVARCHAR(255) NULL,
    TaskStatus VARCHAR(50) NULL,
    TaskBypass VARCHAR(50) NULL,
    TaskAssignee VARCHAR(50) NULL,
    TaskAssigneeAccount VARCHAR(50) NULL,
    TaskAssigneeName NVARCHAR(50) NULL,
    TaskCreateTime DATETIME2 NULL,
    TaskClaimTime DATETIME2 NULL,
    TaskEndTime DATETIME2 NULL,
    TaskDurationMinutes FLOAT NULL,
    TaskWorkMinutes FLOAT NULL,
    DeleteReason NVARCHAR(255) NULL,
    SyncTime DATETIME2 NULL,
    LastUpdatedTime DATETIME2 NULL,
    TaskCreateDate DATE NULL,
    TaskClaimDate DATE NULL,
    TaskEndDate DATE NULL
);
GO


-- 2. HR_Employee - 員工主檔 (52 欄)
CREATE TABLE HR_Employee (
    EmpCode VARCHAR(8) NOT NULL,
    EmpName NVARCHAR(100) NULL,
    DisplayName NVARCHAR(100) NULL,
    UnicodeName NVARCHAR(100) NULL,
    EnglishName NVARCHAR(100) NULL,
    FirstName NVARCHAR(50) NULL,
    MiddleName NVARCHAR(50) NULL,
    LastName NVARCHAR(50) NULL,
    ADAccount VARCHAR(30) NULL,
    ADDomain NVARCHAR(254) NULL,
    TerminateDate DATETIME NULL,
    Email VARCHAR(50) NULL,
    ExtNo VARCHAR(30) NULL,
    DeptCode VARCHAR(12) NULL,
    DeptCodeLname NVARCHAR(200) NULL,
    DeptCodeEname NVARCHAR(200) NULL,
    CostCenterCode VARCHAR(12) NULL,
    CostCenterLname NVARCHAR(200) NULL,
    SuperiorDeptCode VARCHAR(12) NULL,
    SuperiorDeptLname NVARCHAR(200) NULL,
    SuperiorDeptEname NVARCHAR(200) NULL,
    Supervisor VARCHAR(8) NULL,
    FactoryCode VARCHAR(5) NULL,
    FactoryLname NVARCHAR(30) NULL,
    FactoryEname NVARCHAR(50) NULL,
    BGID INT NULL,
    BGShortName NVARCHAR(15) NULL,
    BUID INT NULL,
    BUShortName NVARCHAR(15) NULL,
    CompanyCode VARCHAR(4) NULL,
    CompanyLname NVARCHAR(200) NULL,
    CompanyEname NVARCHAR(200) NULL,
    SAPCompanyCode VARCHAR(4) NULL,
    AreaID VARCHAR(4) NULL,
    AreaLname NVARCHAR(20) NULL,
    AreaEname NVARCHAR(20) NULL,
    GenderID TINYINT NULL,
    GenderLname NVARCHAR(50) NULL,
    GenderEname VARCHAR(50) NULL,
    Shift VARCHAR(10) NULL,
    OrgUnitCode VARCHAR(12) NULL,
    OrgUnitLname NVARCHAR(200) NULL,
    OrgUnitEname NVARCHAR(200) NULL,
    OrgUnitMgrEmpNo VARCHAR(8) NULL,
    JobFamilyCode VARCHAR(2) NULL,
    JobFamilyName NVARCHAR(100) NULL,
    JobFamilyEName NVARCHAR(100) NULL,
    DeptEmpCode VARCHAR(8) NULL,
    DeptEmpName NVARCHAR(200) NULL,
    CostCenterEname NVARCHAR(200) NULL,
    ModifyDate DATETIME NULL,
    JobCode CHAR(7) NULL
);
GO

-- 3. ProcessRoleUserMapping - 角色-員工對應 (12 欄)
CREATE TABLE ProcessRoleUserMapping (
    ID INT NOT NULL PRIMARY KEY,
    RoleId VARCHAR(20) NOT NULL,
    Plant VARCHAR(25) NOT NULL,
    Factory VARCHAR(25) NULL,
    ProductionArea VARCHAR(25) NULL,
    LineName VARCHAR(30) NULL,
    EmpCode VARCHAR(8) NOT NULL,
    Updater VARCHAR(8) NULL,
    UpdateDatetime DATETIME NULL,
    UpdateCount INT NOT NULL,
    Creator VARCHAR(8) NULL,
    CreateDatetime DATETIME NULL
);
GO

-- 4. ProcessRoleGroup - 角色群組定義 (8 欄)
CREATE TABLE ProcessRoleGroup (
    GroupCode VARCHAR(20) NOT NULL PRIMARY KEY,
    GroupName NVARCHAR(100) NOT NULL,
    Updater VARCHAR(8) NOT NULL,
    UpdateDatetime DATETIME NOT NULL,
    UpdateCount INT NOT NULL,
    Creator VARCHAR(8) NULL,
    CreateDatetime DATETIME NULL,
    DisplayOrder INT NULL
);
GO


-- 5. ProcessRoleGroupMapping - 角色群組對應 (12 欄)
CREATE TABLE ProcessRoleGroupMapping (
    ID INT NOT NULL PRIMARY KEY,
    Plant VARCHAR(25) NOT NULL,
    GroupCode VARCHAR(20) NOT NULL,
    RoleId VARCHAR(20) NOT NULL,
    LinkSupervisor CHAR(1) NOT NULL,
    RoleExchangedBy VARCHAR(25) NOT NULL,
    Updater VARCHAR(25) NULL,
    UpdateDatetime DATETIME NULL,
    UpdateCount INT NOT NULL,
    Creator VARCHAR(8) NULL,
    CreateDatetime DATETIME NULL,
    Factory VARCHAR(25) NOT NULL
);
GO

-- 6. EmpNodeRoleMapping - 員工-節點角色 (5 欄)
CREATE TABLE EmpNodeRoleMapping (
    EmpCode VARCHAR(50) NOT NULL,
    NodeCode VARCHAR(15) NOT NULL,
    UpdateTime DATETIME NOT NULL,
    UpdateEmp VARCHAR(25) NOT NULL,
    Vx VARCHAR(4) NOT NULL,
    PRIMARY KEY (EmpCode, NodeCode, Vx)
);
GO

-- 7. EmpOrgInfoMapping - 員工-組織對應 (5 欄)
CREATE TABLE EmpOrgInfoMapping (
    EmpCode VARCHAR(25) NOT NULL,
    Plant VARCHAR(25) NOT NULL,
    MFGFactoryId VARCHAR(25) NOT NULL,
    UpdateTime DATETIME NOT NULL,
    UpdateEmp VARCHAR(25) NOT NULL,
    PRIMARY KEY (EmpCode, Plant, MFGFactoryId)
);
GO

-- 8. EmpUserGroupMapping - 員工-群組對應 (4 欄)
CREATE TABLE EmpUserGroupMapping (
    EmpCode VARCHAR(25) NOT NULL,
    UserGroupId INT NOT NULL,
    UpdateTime DATETIME NOT NULL,
    UpdateEmp VARCHAR(25) NOT NULL,
    PRIMARY KEY (EmpCode, UserGroupId)
);
GO

-- 9. UserGroup - 使用者群組定義 (5 欄)
CREATE TABLE UserGroup (
    UserGroupId INT NULL,
    UserGroupName NVARCHAR(255) NULL,
    UserGroupDesc NVARCHAR(255) NULL,
    UpdateTime DATETIME NULL,
    UpdateEmp VARCHAR(25) NULL
);
GO

-- 10. DMPFunctionConfig - 功能設定 (12 欄)
CREATE TABLE DMPFunctionConfig (
    ID INT NOT NULL PRIMARY KEY,
    FunctionCode VARCHAR(50) NOT NULL,
    Plant VARCHAR(25) NOT NULL,
    Factory VARCHAR(25) NULL,
    ProductionArea VARCHAR(25) NULL,
    LineName VARCHAR(30) NULL,
    AssignLineFlag CHAR(1) NOT NULL,
    Updater VARCHAR(8) NULL,
    UpdateDatetime DATETIME NULL,
    UpdateCount INT NULL,
    Creator VARCHAR(8) NULL,
    CreateDatetime DATETIME NULL
);
GO

-- 11. DMPFunctionClientMapping - 客戶端對應 (9 欄)
CREATE TABLE DMPFunctionClientMapping (
    ID INT NOT NULL PRIMARY KEY,
    Region NVARCHAR(10) NOT NULL,
    Plant VARCHAR(10) NOT NULL,
    Logsys VARCHAR(10) NULL,
    Updater VARCHAR(8) NULL,
    UpdateDatetime DATETIME NULL,
    UpdateCount INT NOT NULL,
    Creator VARCHAR(8) NULL,
    CreateDatetime DATETIME NULL
);
GO
