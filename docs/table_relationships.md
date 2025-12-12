# 資料表關聯文件

## 概述

本文件說明 Flowable BPM (APP_SRV_BPM) 與 DMP (APP_SRV_COMMON) 資料表之間的關聯關係，供後續 Silver 層 JOIN 使用。

---

## Flowable 表之間的關聯

### 核心關聯圖

```
ACT_RE_PROCDEF (流程定義)
       │
       │ PROC_DEF_ID_ = ID_
       ▼
ACT_HI_PROCINST (流程實例)
       │
       ├── PROC_INST_ID_ ──► ACT_HI_TASKINST (任務實例)
       │                            │
       │                            │ TASK_ID_
       │                            ▼
       │                     ACT_HI_IDENTITYLINK (任務參與者)
       │
       └── PROC_INST_ID_ ──► ACT_HI_VARINST (流程變數)
```

### Join Key 對照表

| 關聯場景 | 左表 | 右表 | Join 條件 |
|----------|------|------|-----------|
| 流程定義 → 流程實例 | ACT_RE_PROCDEF | ACT_HI_PROCINST | `ID_ = PROC_DEF_ID_` |
| 流程實例 → 任務實例 | ACT_HI_PROCINST | ACT_HI_TASKINST | `PROC_INST_ID_ = PROC_INST_ID_` |
| 流程實例 → 流程變數 | ACT_HI_PROCINST | ACT_HI_VARINST | `PROC_INST_ID_ = PROC_INST_ID_` |
| 任務實例 → 參與者 | ACT_HI_TASKINST | ACT_HI_IDENTITYLINK | `ID_ = TASK_ID_` |

---

## DMP 表與 Flowable 的關聯

### 人員維度關聯

```
FlowableTaskStats.TaskAssignee ──► HR_Employee.EmpCode
ACT_HI_TASKINST.ASSIGNEE_ ──► HR_Employee.EmpCode (或 ADAccount)
ACT_HI_IDENTITYLINK.USER_ID_ ──► HR_Employee.EmpCode
```

### 角色/組織維度關聯

```
HR_Employee.EmpCode
       │
       ├──► ProcessRoleUserMapping.EmpCode (員工角色)
       ├──► EmpNodeRoleMapping.EmpCode (節點角色)
       ├──► EmpOrgInfoMapping.EmpCode (組織對應)
       └──► EmpUserGroupMapping.EmpCode (群組對應)
```

---

## 常用 JOIN 範例

### 1. 任務統計 + 員工資訊

```sql
SELECT 
    t.TaskId,
    t.TaskName,
    t.TaskAssignee,
    e.EmpName,
    e.DeptCodeLname as Department,
    e.FactoryLname as Factory
FROM bronze.common_flowable_task_stats t
LEFT JOIN bronze.common_hr_employee e 
    ON t.TaskAssignee = e.EmpCode;
```

### 2. 流程實例 + 流程定義名稱

```sql
SELECT 
    p.PROC_INST_ID_,
    p.START_TIME_,
    p.END_TIME_,
    d.NAME_ as ProcessName,
    d.KEY_ as ProcessKey
FROM bronze.bpm_act_hi_procinst p
LEFT JOIN bronze.bpm_act_re_procdef d 
    ON p.PROC_DEF_ID_ = d.ID_;
```

### 3. 任務 + 處理人 + 員工資訊

```sql
SELECT 
    t.ID_ as TaskId,
    t.NAME_ as TaskName,
    t.ASSIGNEE_,
    e.EmpName,
    e.DeptCodeLname
FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN bronze.common_hr_employee e 
    ON t.ASSIGNEE_ = e.EmpCode;
```
