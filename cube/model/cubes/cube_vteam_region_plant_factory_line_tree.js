/**
 * VTeam Region Plant Factory Line Tree
 * 
 * 用途：VTeam 維度階層樹（Region → Plant → Factory → Line）
 * 來源：MSSQL 直接查詢（跨 BPM + COMMON 資料庫）
 * 
 * 維度階層：
 *   VTeam
 *     └── Region
 *           └── Plant
 *                 └── Factory
 *                       └── ProductionArea
 *                             └── LineName
 */
cube('VTeam_Region_Plant_Factory_Line_Tree', {
  data_source: `datasource1`,
  
  sql: `
    SELECT DISTINCT
      AHT.TASK_DEF_KEY_                  AS task_def_key,
      plantVar.TEXT_                     AS plant,
      SUBSTRING(AHT.TASK_DEF_KEY_, 1, 2) AS vteam,
      b.Region                           AS region,
      a.Factory                          AS factory,
      a.ProductionArea                   AS production_area,
      a.LineName                         AS line_name,
      a.AssignLineFlag                   AS assign_line_flag
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST AHT
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST plantVar
      ON AHT.PROC_INST_ID_ = plantVar.PROC_INST_ID_
     AND plantVar.NAME_ = 'plant'
    JOIN APP_SRV_COMMON.dbo.DMPFunctionConfig a
      ON plantVar.TEXT_ = a.Plant
    LEFT JOIN APP_SRV_COMMON.dbo.DMPFunctionClientMapping b
      ON a.Plant = b.Plant
    WHERE UPPER(AHT.TASK_DEF_KEY_) LIKE 'V%'
  `,

  measures: {
    count: {
      type: 'count',
      drillMembers: [
        'taskDefKey',
        'vteam',
        'region',
        'plant',
        'factory',
        'lineName'
      ]
    }
  },

  dimensions: {
    taskDefKey: {
      sql: 'task_def_key',
      type: 'string'
    },
    vteam: {
      sql: 'vteam',
      type: 'string'
    },
    region: {
      sql: 'region',
      type: 'string'
    },
    plant: {
      sql: 'plant',
      type: 'string'
    },
    factory: {
      sql: 'factory',
      type: 'string'
    },
    productionArea: {
      sql: 'production_area',
      type: 'string'
    },
    lineName: {
      sql: 'line_name',
      type: 'string'
    },
    assignLineFlag: {
      sql: 'assign_line_flag',
      type: 'string'
    }
  }
});
