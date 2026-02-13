BEGIN
    DECLARE @CurrentTime DATETIME2 = GETDATE();
    DECLARE @AGGDATE DATETIME = DATEADD(DAY, - 1, CAST(GETDATE() AS DATE));
    DECLARE @AGGWEEK NVARCHAR(10) = DATEPART(ISO_WEEK , GETDATE());
    DECLARE @AGGYearForWeek NVARCHAR(10) = dbo.GetISOYear(GETDATE())
    DECLARE @AGGMONTH NVARCHAR(10) = DATEPART(Month , GETDATE());
    DECLARE @AGGYEAR NVARCHAR(10) = DATEPART(Year , GETDATE());
    DECLARE @RowCount INT = 0;
    PRINT N'数据汇算开始 ' + CONVERT(VARCHAR, @CurrentTime, 120);
    -- 日
    MERGE INTO RptCommonKpiTaskComplete AS target
    USING (
        SELECT mfam.MFG_SITE AS Region,
               fts.Plant,
               fts.Factory,
               fts.ProductionArea,
               fts.Line,
               SUM(CASE
                       WHEN TaskCreateDate = @AGGDATE AND
                            (TaskClaimDate <> @AGGDATE OR TaskClaimDate IS NULL) AND
                            (TaskEndDate <> @AGGDATE OR TaskEndDate IS NULL)
                           THEN 1 ELSE 0
                   END) AS Todo,
               SUM(CASE
                       WHEN TaskClaimDate =  @AGGDATE AND
                            (TaskEndDate <>  @AGGDATE OR TaskEndDate IS NULL)
                           THEN 1 ELSE 0
                   END) AS Doing,
               SUM(CASE
                       WHEN TaskEndDate = @AGGDATE THEN 1
                       ELSE 0 END) AS Done,
               SUM(CASE
                       WHEN fts.TaskCreateDate BETWEEN DATEADD(day, -6, @AGGDATE) AND @AGGDATE
                           AND (fts.TaskEndDate IS NULL OR fts.TaskEndDate NOT BETWEEN DATEADD(day, -6, @AGGDATE) AND @AGGDATE)
                           THEN 1 ELSE 0
                   END) AS Acc,
               SUM(CASE
                       WHEN fts.TaskCreateDate BETWEEN DATEADD(day, -6, @AGGDATE) AND @AGGDATE
                           THEN 1 ELSE 0
                   END) AS TotalTask,
               CASE
                   WHEN ((fts.Factory = 'NPE' OR fts.Factory LIKE '%NPE%') OR
                         (LEFT(fts.MoNumber, 3) IN ('196', '199', '200', '210', '212', '213') OR LEFT(fts.MoNumber, 3) IS NULL)) AND
                        ProcessTeam <> 'V2' THEN 'V1'
                   ELSE fts.ProcessTeam END ProcessVxTeam,
               LEFT(fts.MoNumber, 3) MoNumberPrefix,
               @AGGDATE Date
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats fts
                 LEFT JOIN MDM_FACTORY_AREA_MASTER mfam on fts.Plant = mfam.FACTORY
        WHERE fts.TaskBypass = 'N'
          AND fts.TaskCreateDate BETWEEN DATEADD(day, -6, @AGGDATE) AND @AGGDATE
          AND fts.ProcessDefinitionKey NOT LIKE 'E%'
        GROUP BY fts.ProcessTeam,
                 fts.Plant,
                 fts.Factory,
                 fts.ProductionArea,
                 fts.Line,
                 mfam.MFG_SITE,
                 Left(fts.MoNumber, 3)
    ) AS source
    ON target.Date = source.Date
        AND ISNULL(target.Region,'') = ISNULL(source.Region,'')
        AND ISNULL(target.Plant,'') = ISNULL(source.Plant,'')
        AND ISNULL(target.Factory,'') = ISNULL(source.Factory,'')
        AND ISNULL(target.ProductionArea,'') = ISNULL(source.ProductionArea,'')
        AND ISNULL(target.Line,'') = ISNULL(source.Line,'')
        AND ISNULL(target.MoNumberPrefix,'') = ISNULL(source.MoNumberPrefix,'')
        AND target.ProcessVxTeam = source.ProcessVxTeam
    WHEN MATCHED THEN
        UPDATE SET
                   target.Todo = source.Todo,
                   target.Doing = source.Doing,
                   target.Done = source.Done,
                   target.Acc = source.Acc,
                   target.TotalTask = source.TotalTask
    WHEN NOT MATCHED THEN
        INSERT (Region, Plant, Factory, ProductionArea, Line, Todo, Doing, Done, ProcessVxTeam, MoNumberPrefix, [Date],Acc,TotalTask)
        VALUES (source.Region, source.Plant, source.Factory, source.ProductionArea, source.Line,
                source.Todo, source.Doing, source.Done, source.ProcessVxTeam, source.MoNumberPrefix,
                source.Date,source.Acc,source.TotalTask);
    PRINT N'日MERGE执行完成，影响行数：' + CAST(@@ROWCOUNT AS NVARCHAR(10));
End
 