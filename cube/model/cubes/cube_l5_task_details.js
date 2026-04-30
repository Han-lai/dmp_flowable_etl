/**
 * L5 任務明細 Cube (Detail View)
 *
 * 目的：提供「原始任務明細表」的查詢能力，供使用者在 Superset 或 BI 工具中
 *       鑽取到單一任務層級的明細資料（Task ID、工單號、時間戳記等）。
 *
 * 關鍵設計：
 * 1. 使用 FINAL 關鍵字：silver.mv_fact_task_vx 是 ReplacingMergeTree，
 *    若不加 FINAL，ClickHouse 會返回尚未被合併的重複歷史版本，造成資料重複。
 * 2. 限制回傳欄位：只暴露業務需要的欄位，避免使用者接觸到系統內部欄位。
 * 3. 不做時光機聚合：此 Cube 是單純的明細表，所有過濾都是標準的 WHERE 條件。
 *
 * ⚠️ 注意事項：
 * - 此 Cube 的 `sql` 使用了 FINAL，在 ClickHouse 中 FINAL 會使查詢稍慢，
 *   但這是確保明細資料正確性的必要代價。
 * - 不建議在此 Cube 上建立大量聚合指標，KPI 聚合請使用 L5TaskPeriodic Cube。
 */
cube(`L5TaskDetails`, {
    sql: `
        -- ⚠️ FINAL 是此 Cube 的核心設計，確保從 ReplacingMergeTree 讀取去重後的唯一版本
        SELECT
            -- [識別欄位]
            task_id,
            proc_inst_id,
            task_definition_key,
            task_name,

            -- [時間欄位]
            task_start_date,
            task_claim_date,
            task_end_date,
            task_start_time,
            task_claim_time,
            task_end_time,

            -- [狀態欄位] - 三個 Cohort 結算週期，對應 KPI Cube 的 daily/weekly/monthly 指標
            status_daily,
            status_weekly,
            status_monthly,

            -- [製造維度]
            vx_type,
            region,
            plant,
            factory,
            line,

            -- [業務變數 - 11 欄]
            mo_number,
            model_name,
            delivery_area,
            schedule_number,
            sap_plant,
            sap_product_group,
            pallet,
            transfer_no,
            qblock_event_id,
            defect_sn,

            -- [效能指標]
            duration_min,
            processing_time_min,

            -- [L4 流程資訊]
            l4_process_id,
            l4_process_name

        FROM silver.mv_fact_task_vx FINAL
        -- 排除系統自動過帳、虛擬任務等無效任務
        WHERE is_excluded = 0
    `,

    // =========================================================
    // 維度 (Dimensions)
    // =========================================================
    dimensions: {
        // [主鍵] 任務唯一識別 ID
        taskId: {
            sql: `task_id`,
            type: `string`,
            primaryKey: true,
            shown: true
        },

        // 流程實例 ID（一個工單對應的所有任務共享同一個 proc_inst_id）
        procInstId: {
            sql: `proc_inst_id`,
            type: `string`,
            title: `流程實例 ID`
        },

        // 任務定義 Key（對應業務分類的流程步驟代碼）
        taskDefinitionKey: {
            sql: `task_definition_key`,
            type: `string`,
            title: `任務定義 Key`
        },

        // 任務名稱（前台顯示名稱）
        taskName: {
            sql: `task_name`,
            type: `string`,
            title: `任務名稱`
        },

        // 日結算狀態：開單日當天作為結算截止點，對應 KPI Cube 的 todo_daily/doing_daily/done_daily
        statusDaily: {
            sql: `status_daily`,
            type: `string`,
            title: `日結算狀態`
        },

        // 週結算狀態：開單日所在週的週日作為結算截止點，對應 KPI Cube 的 todo_weekly/doing_weekly/done_weekly
        statusWeekly: {
            sql: `status_weekly`,
            type: `string`,
            title: `週結算狀態`
        },

        // 月結算狀態：開單日所在月的月底作為結算截止點，對應 KPI Cube 的 todo_monthly/doing_monthly/done_monthly
        statusMonthly: {
            sql: `status_monthly`,
            type: `string`,
            title: `月結算狀態`
        },

        // --- 製造維度 ---
        vxType: {
            sql: `vx_type`,
            type: `string`,
            title: `業務分類 (VX Type)`
        },

        region: {
            sql: `region`,
            type: `string`,
            title: `區域`
        },

        plant: {
            sql: `plant`,
            type: `string`,
            title: `廠別`
        },

        factory: {
            sql: `factory`,
            type: `string`,
            title: `工廠`
        },

        line: {
            sql: `line`,
            type: `string`,
            title: `線別`
        },

        // --- 業務變數 ---
        moNumber: {
            sql: `mo_number`,
            type: `string`,
            title: `工單號`
        },

        modelName: {
            sql: `model_name`,
            type: `string`,
            title: `機種`
        },

        deliveryArea: {
            sql: `delivery_area`,
            type: `string`,
            title: `交付區域`
        },

        scheduleNumber: {
            sql: `schedule_number`,
            type: `string`,
            title: `排程編號`
        },

        sapPlant: {
            sql: `sap_plant`,
            type: `string`,
            title: `SAP 廠別`
        },

        sapProductGroup: {
            sql: `sap_product_group`,
            type: `string`,
            title: `SAP 產品組`
        },

        // --- L4 流程資訊 ---
        l4ProcessId: {
            sql: `l4_process_id`,
            type: `string`,
            title: `L4 流程 ID`
        },

        l4ProcessName: {
            sql: `l4_process_name`,
            type: `string`,
            title: `L4 流程名稱`
        },

        // --- 時間維度 ---
        taskStartDate: {
            sql: `task_start_date`,
            type: `time`,
            title: `開單日期`
        },

        taskClaimDate: {
            sql: `task_claim_date`,
            type: `time`,
            title: `簽收日期`
        },

        taskEndDate: {
            sql: `task_end_date`,
            type: `time`,
            title: `完成日期`
        },

        // --- 效能指標 (當維度使用) ---
        durationMin: {
            sql: `duration_min`,
            type: `number`,
            title: `總持續時間 (分鐘)`
        },

        processingTimeMin: {
            sql: `processing_time_min`,
            type: `number`,
            title: `實際處理時間 (分鐘)`
        },
    },

    // =========================================================
    // 指標 (Measures)
    // =========================================================
    measures: {
        // 任務總數（去重計數）
        taskCount: {
            sql: `task_id`,
            type: `count_distinct`,
            title: `任務總數`
        },

        // 平均處理時間
        avgProcessingTimeMin: {
            sql: `processing_time_min`,
            type: `avg`,
            title: `平均處理時間 (分鐘)`
        },
    },

});
