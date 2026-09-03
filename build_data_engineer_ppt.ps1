$ErrorActionPreference = "Stop"

function Rgb($r, $g, $b) {
    return ($r + ($g * 256) + ($b * 65536))
}

$colors = @{
    Navy = Rgb 24 48 85
    Blue = Rgb 43 91 154
    LightBlue = Rgb 230 240 252
    Green = Rgb 44 130 95
    LightGreen = Rgb 229 245 238
    Gray = Rgb 110 118 130
    LightGray = Rgb 242 244 247
    Dark = Rgb 32 38 46
    White = Rgb 255 255 255
    Border = Rgb 205 213 223
    Amber = Rgb 184 124 32
    LightAmber = Rgb 255 246 226
}

$font = "Microsoft JhengHei"
$outPath = "D:\000_preparecv\製造業資料工程與資料平台實踐.pptx"

function Add-Text($slide, $text, $x, $y, $w, $h, $size = 20, $bold = $false, $color = $colors.Dark, $align = 1) {
    $shape = $slide.Shapes.AddTextbox(1, $x, $y, $w, $h)
    $range = $shape.TextFrame.TextRange
    $range.Text = $text
    $range.Font.Name = $font
    $range.Font.Size = $size
    $range.Font.Color.RGB = $color
    $range.Font.Bold = [int]$bold
    $range.ParagraphFormat.Alignment = $align
    $shape.TextFrame.MarginLeft = 6
    $shape.TextFrame.MarginRight = 6
    $shape.TextFrame.MarginTop = 4
    $shape.TextFrame.MarginBottom = 4
    return $shape
}

function Add-Title($slide, $title, $subtitle = "") {
    Add-Text $slide $title 44 26 600 42 26 $true $colors.Navy 1 | Out-Null
    if ($subtitle -ne "") {
        Add-Text $slide $subtitle 46 64 620 26 13 $false $colors.Gray 1 | Out-Null
    }
    $line = $slide.Shapes.AddShape(1, 44, 91, 872, 1.5)
    $line.Fill.ForeColor.RGB = $colors.Border
    $line.Line.Visible = 0
}

function Add-Box($slide, $text, $x, $y, $w, $h, $fill, $line, $size = 15, $bold = $false, $fontColor = $colors.Dark) {
    $shape = $slide.Shapes.AddShape(5, $x, $y, $w, $h)
    $shape.Fill.ForeColor.RGB = $fill
    $shape.Line.ForeColor.RGB = $line
    $shape.Line.Weight = 1
    $shape.TextFrame.TextRange.Text = $text
    $shape.TextFrame.TextRange.Font.Name = $font
    $shape.TextFrame.TextRange.Font.Size = $size
    $shape.TextFrame.TextRange.Font.Bold = [int]$bold
    $shape.TextFrame.TextRange.Font.Color.RGB = $fontColor
    $shape.TextFrame.TextRange.ParagraphFormat.Alignment = 2
    $shape.TextFrame.VerticalAnchor = 3
    $shape.TextFrame.MarginLeft = 8
    $shape.TextFrame.MarginRight = 8
    $shape.TextFrame.MarginTop = 5
    $shape.TextFrame.MarginBottom = 5
    return $shape
}

function Add-Line($slide, $x1, $y1, $x2, $y2, $color = $colors.Gray, $weight = 1.5, $arrow = $true) {
    $line = $slide.Shapes.AddConnector(1, $x1, $y1, $x2, $y2)
    $line.Line.ForeColor.RGB = $color
    $line.Line.Weight = [int][math]::Round($weight)
    if ($arrow) { $line.Line.EndArrowheadStyle = 3 }
    return $line
}

function Add-Notes($slide, $notes) {
    try {
        $slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = $notes
        $slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Font.Name = $font
    } catch {
        # Notes placeholder may vary by Office version.
    }
}

function Add-StatusLegend($slide, $x, $y) {
    Add-Box $slide "實際參與" $x $y 86 24 $colors.LightBlue $colors.Blue 11 $true $colors.Blue | Out-Null
    Add-Box $slide "技術選型驗證" ($x + 96) $y 104 24 $colors.LightGreen $colors.Green 11 $true $colors.Green | Out-Null
    Add-Box $slide "後續規劃" ($x + 210) $y 86 24 $colors.LightGray $colors.Gray 11 $true $colors.Gray | Out-Null
}

$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = 1
$pres = $ppt.Presentations.Add()
$pres.PageSetup.SlideWidth = 960
$pres.PageSetup.SlideHeight = 540

# P1
$slide = $pres.Slides.Add(1, 12)
$slide.Background.Fill.ForeColor.RGB = Rgb 247 249 252
Add-Text $slide "製造業資料工程與資料平台實踐" 70 170 820 60 34 $true $colors.Navy 2 | Out-Null
Add-Text $slide "從資料接入到 BI 資料產品" 70 238 820 34 20 $false $colors.Blue 2 | Out-Null
$labels = @("來源系統", "資料接入", "資料處理", "資料儲存", "資料交付")
for ($i = 0; $i -lt $labels.Count; $i++) {
    $x = 105 + ($i * 152)
    Add-Box $slide $labels[$i] $x 338 116 42 $colors.White $colors.Border 13 $true $colors.Navy | Out-Null
    if ($i -lt $labels.Count - 1) { Add-Line $slide ($x + 116) 359 ($x + 150) 359 $colors.Blue 1.8 $true | Out-Null }
}
Add-Notes $slide "這份簡報聚焦我的資料工程師職責與能力範圍。三個專案只作為能力證據，用來說明我如何處理資料接入、轉換、儲存、品質、可靠性與交付。"

# P2
$slide = $pres.Slides.Add(2, 12)
Add-Title $slide "P2｜我的角色定位" "核心訊息：建立來源系統到資料使用者之間的穩定資料供應鏈"
Add-Box $slide "來源系統`nMES / EAP`nFlowable / MSSQL`nKafka" 70 185 210 120 $colors.LightGray $colors.Border 17 $true $colors.Dark | Out-Null
Add-Box $slide "資料工程師`n接入、處理、儲存`n品質、維運、交付" 365 165 230 160 $colors.LightBlue $colors.Blue 18 $true $colors.Navy | Out-Null
Add-Box $slide "資料使用者`nBI / Dashboard`nAPI / 報表`n製造分析" 680 185 210 120 $colors.LightGray $colors.Border 17 $true $colors.Dark | Out-Null
Add-Line $slide 280 245 365 245 $colors.Blue 2 $true | Out-Null
Add-Line $slide 595 245 680 245 $colors.Blue 2 $true | Out-Null
Add-Notes $slide "我的角色不是單純將資料搬到資料庫，而是讓資料能被保存、整理、驗證、查詢與交付。工作範圍橫跨來源理解、管線設計、資料處理、儲存設計、品質檢查與資料交付。"

# P3
$slide = $pres.Slides.Add(3, 12)
Add-Title $slide "P3｜業務背景與資料問題" "核心訊息：製造資料分散，導致資料難以重用"
$sources = @("MES", "EAP", "Flowable", "MDM", "HR", "ERP")
for ($i = 0; $i -lt $sources.Count; $i++) {
    $x = 65 + (($i % 3) * 120)
    $y = 150 + ([math]::Floor($i / 3) * 90)
    Add-Box $slide $sources[$i] $x $y 88 48 $colors.White $colors.Border 16 $true $colors.Navy | Out-Null
}
Add-Box $slide "資料孤島`n格式不一致`n重複開發`n難以重用`n分析影響來源系統" 420 145 180 178 $colors.LightAmber $colors.Amber 17 $true $colors.Dark | Out-Null
Add-Box $slide "目標`n統一、可追蹤`n可重用的資料供應" 705 175 185 118 $colors.LightBlue $colors.Blue 18 $true $colors.Navy | Out-Null
Add-Line $slide 365 240 420 240 $colors.Amber 2 $true | Out-Null
Add-Line $slide 600 240 705 240 $colors.Blue 2 $true | Out-Null
Add-Notes $slide "製造現場資料分散在不同系統，每個系統有不同資料格式與使用情境。資料工程的價值，是建立穩定、可追蹤、可重用的資料流。"

# P4
$slide = $pres.Slides.Add(4, 12)
Add-Title $slide "P4｜整體資料流" "核心訊息：用橫向端到端流程說明資料供應鏈"
$stages = @(
    @("資料來源", "MES / EAP`nFlowable / MSSQL"),
    @("資料接入", "Kafka：即時訊息平台`nODBC：資料庫連線介面"),
    @("流程編排", "Airflow：排程與編排`nSeaTunnel：資料同步整合`nCron：定時排程"),
    @("資料處理", "Python / SQL`nJSON / Join"),
    @("資料儲存", "S3 / MinIO / Parquet`nClickHouse / Doris"),
    @("資料交付", "Cube.js：BI 語義層`nBI / API / 報表")
)
for ($i = 0; $i -lt $stages.Count; $i++) {
    $x = 38 + ($i * 152)
    Add-Box $slide $stages[$i][0] $x 150 126 38 $colors.Blue $colors.Blue 15 $true $colors.White | Out-Null
    Add-Box $slide $stages[$i][1] $x 192 126 96 $colors.White $colors.Border 11 $false $colors.Dark | Out-Null
    if ($i -lt $stages.Count - 1) { Add-Line $slide ($x + 126) 220 ($x + 150) 220 $colors.Blue 1.6 $true | Out-Null }
}
Add-Box $slide "製造分析與決策" 382 342 196 48 $colors.LightGreen $colors.Green 18 $true $colors.Green | Out-Null
Add-Line $slide 492 288 492 342 $colors.Green 1.8 $true | Out-Null
Add-Notes $slide "這頁從端到端角度說明資料如何流動。技術名稱不是重點，重點是每個工具在資料供應鏈中負責哪一段。P4 採橫向流程，適合 16:9 投影。"

# P5
$slide = $pres.Slides.Add(5, 12)
Add-Title $slide "P5｜我的主要職責" "核心訊息：能力範圍涵蓋資料管線完整生命週期"
$items = @(
    "多來源資料接入`nKafka、MSSQL、ClickHouse",
    "ETL / EL Pipeline`n抽取、載入、轉換",
    "Batch / Stream / Incremental / Backfill`n批次、串流、增量、回補",
    "資料建模與分層`nBronze、Silver、Gold",
    "資料品質與對帳`n筆數、完整性、成功率",
    "可靠性與錯誤處理`nretry、offset、watermark",
    "效能與記憶體管理`nbatch size、memory limit",
    "監控與維運`nlog、metrics、Dashboard"
)
for ($i = 0; $i -lt $items.Count; $i++) {
    $x = 55 + (($i % 4) * 218)
    $y = 138 + ([math]::Floor($i / 4) * 145)
    Add-Box $slide $items[$i] $x $y 190 96 $colors.White $colors.Border 14 $true $colors.Navy | Out-Null
}
Add-Notes $slide "我的職責不是單點工具操作，而是涵蓋資料管線完整生命週期。從接資料、處理資料，到確保資料可靠、可維護、可交付。"

# P6
$slide = $pres.Slides.Add(6, 12)
Add-Title $slide "P6｜資料平台分層" "核心訊息：資料由原始保存逐步轉為可交付資料產品"
$layers = @(
    @("Raw / Bronze", "保存原始資料與同步紀錄`nCFX Raw Data Lake、MSSQL ODBC、_sync_watermark"),
    @("Silver", "清洗、Pivot、Join、Fact / Dimension`nEAV 變數轉置、五階製造維度對齊"),
    @("Gold", "KPI、聚合、預計算`nL5 任務完成率、Todo / Doing / Done、滾動 ACC"),
    @("Data Delivery", "Cube.js、BI、API、報表`n統一語義層，避免前端直連資料庫")
)
for ($i = 0; $i -lt $layers.Count; $i++) {
    $y = 360 - ($i * 78)
    $fill = @($colors.LightGray, $colors.LightBlue, $colors.LightGreen, $colors.LightAmber)[$i]
    $line = @($colors.Gray, $colors.Blue, $colors.Green, $colors.Amber)[$i]
    Add-Box $slide $layers[$i][0] 90 $y 170 54 $fill $line 17 $true $line | Out-Null
    Add-Box $slide $layers[$i][1] 282 $y 585 54 $colors.White $colors.Border 13 $false $colors.Dark | Out-Null
}
Add-Notes $slide "分層的目的，是讓資料從原始狀態逐步變成可分析、可交付的資料。CFX 主要支撐 Raw / Bronze；DMP Flowable 涵蓋 Bronze、Silver、Gold 到 Cube.js；Doris-SeaTunnel POC 驗證資料匯流與 Doris 儲存能力。"

# P7
$slide = $pres.Slides.Add(7, 12)
Add-Title $slide "P7｜三個專案如何支援我的能力" "核心訊息：專案是能力證據，不是三個獨立介紹"
Add-StatusLegend $slide 600 102
$headers = @("能力面向", "CFX Kafka`nAirflow ETL", "Doris-SeaTunnel`nETL POC", "DMP Flowable`nETL")
$colX = @(40, 225, 450, 675)
$colW = @(170, 200, 200, 200)
for ($i = 0; $i -lt $headers.Count; $i++) { Add-Box $slide $headers[$i] $colX[$i] 138 $colW[$i] 42 $colors.Blue $colors.Blue 12 $true $colors.White | Out-Null }
$rows = @(
    @("資料接入", "實際參與", "技術選型驗證", "實際參與"),
    @("流程編排", "實際參與", "技術選型驗證 / 後續規劃", "實際參與"),
    @("資料轉換", "實際參與", "技術選型驗證", "實際參與"),
    @("資料儲存", "實際參與", "技術選型驗證", "實際參與"),
    @("資料建模", "後續規劃", "技術選型驗證", "實際參與"),
    @("資料交付", "後續規劃", "後續規劃", "實際參與"),
    @("監控維運", "實際參與", "未涉及或後續規劃", "實際參與")
)
for ($r = 0; $r -lt $rows.Count; $r++) {
    $y = 180 + ($r * 39)
    Add-Box $slide $rows[$r][0] $colX[0] $y $colW[0] 36 $colors.White $colors.Border 11 $true $colors.Navy | Out-Null
    for ($c = 1; $c -lt 4; $c++) {
        $status = $rows[$r][$c]
        if ($status -like "*實際參與*") { $fill = $colors.LightBlue; $line = $colors.Blue; $textColor = $colors.Blue }
        elseif ($status -like "*技術選型驗證*") { $fill = $colors.LightGreen; $line = $colors.Green; $textColor = $colors.Green }
        else { $fill = $colors.LightGray; $line = $colors.Gray; $textColor = $colors.Gray }
        Add-Box $slide $status $colX[$c] $y $colW[$c] 36 $fill $line 10 $true $textColor | Out-Null
    }
}
Add-Notes $slide "這頁用能力矩陣說明三個專案如何支撐我的資料工程能力。CFX 是實際參與，重點在 Kafka、Airflow、S3、offset 與監控；Doris-SeaTunnel 是技術選型驗證；DMP Flowable 是實際參與，重點在 ClickHouse 分層、Gold 聚合與 Cube.js 交付。"

# P8
$slide = $pres.Slides.Add(8, 12)
Add-Title $slide "P8｜資料可靠性" "核心訊息：資料管線要可追蹤、可重跑、可避免重複"
Add-Box $slide "成功路徑" 70 132 120 34 $colors.LightBlue $colors.Blue 14 $true $colors.Blue | Out-Null
$success = @("資料處理", "成功寫入", "Watermark / Offset / Checkpoint")
for ($i = 0; $i -lt $success.Count; $i++) {
    $x = 220 + ($i * 195)
    Add-Box $slide $success[$i] $x 125 150 48 $colors.White $colors.Border 13 $true $colors.Navy | Out-Null
    if ($i -lt $success.Count - 1) { Add-Line $slide ($x + 150) 149 ($x + 190) 149 $colors.Blue 2 $true | Out-Null }
}
Add-Box $slide "失敗路徑" 70 250 120 34 $colors.LightAmber $colors.Amber 14 $true $colors.Amber | Out-Null
$fail = @("資料處理失敗", "Retry / Backfill", "重跑", "DELETE-INSERT /`nReplacingMergeTree 去重")
for ($i = 0; $i -lt $fail.Count; $i++) {
    $x = 220 + ($i * 155)
    Add-Box $slide $fail[$i] $x 240 130 58 $colors.White $colors.Border 12 $true $colors.Dark | Out-Null
    if ($i -lt $fail.Count - 1) { Add-Line $slide ($x + 130) 269 ($x + 150) 269 $colors.Amber 1.8 $true | Out-Null }
}
Add-Box $slide "目標：降低資料遺失風險，讓結果一致且可恢復" 220 372 520 48 $colors.LightGreen $colors.Green 17 $true $colors.Green | Out-Null
Add-Notes $slide "CFX 專案中，Kafka offset 只在 S3 Parquet 成功寫入後 commit。指定日期重跑時，透過 DELETE 既有 partition，再重新消費相同 offset range，避免重複資料。DMP Flowable 透過 _sync_watermark 追蹤同步進度。"

# P9
$slide = $pres.Slides.Add(9, 12)
Add-Title $slide "P9｜資料品質、效能與監控" "核心訊息：穩定資料管線來自品質、資源與可觀測性"
$cols = @(
    @("品質檢核", "processed vs expected`ndata loss rate`ntopic success rate`nfile integrity`nwatermark / offset 狀態"),
    @("效能與資源", "batch size`nmemory limit`nmicro-batch`nDuckDB threads`n分區與預聚合"),
    @("可觀測性", "Airflow log`nstructured log`nOTEL metrics`nPrometheus`nGrafana")
)
for ($i = 0; $i -lt 3; $i++) {
    $x = 78 + ($i * 285)
    Add-Box $slide $cols[$i][0] $x 140 230 42 $colors.Blue $colors.Blue 17 $true $colors.White | Out-Null
    Add-Box $slide $cols[$i][1] $x 188 230 190 $colors.White $colors.Border 17 $false $colors.Dark | Out-Null
}
Add-Notes $slide "品質檢核確保資料是否完整、成功、可追蹤。效能與資源管理用來避免大型訊息或大量資料造成 OOM 或查詢效能問題。可觀測性讓任務失敗、資料落差與效能瓶頸可以被追蹤。"

# P10
$slide = $pres.Slides.Add(10, 12)
Add-Title $slide "P10｜跨團隊協作" "核心訊息：資料工程師串起需求、來源、平台與交付"
Add-Box $slide "資料工程師" 390 225 180 72 $colors.LightBlue $colors.Blue 20 $true $colors.Navy | Out-Null
$teams = @(
    @("製造 / 業務", "分析需求、KPI`n使用情境", 90, 135),
    @("來源系統 / DB", "資料來源、欄位邏輯`n唯讀限制", 650, 135),
    @("IT / Infra", "環境、權限`n容器與監控資源", 90, 345),
    @("BI / 應用", "語義層、Dashboard`nAPI、報表需求", 650, 345)
)
foreach ($team in $teams) {
    Add-Box $slide ($team[0] + "`n" + $team[1]) $team[2] $team[3] 220 78 $colors.White $colors.Border 14 $true $colors.Dark | Out-Null
    Add-Line $slide ($team[2] + 110) ($team[3] + 39) 480 261 $colors.Blue 1.6 $true | Out-Null
}
Add-Notes $slide "資料工程師需要把業務需求、來源限制、平台能力與交付方式串起來。DMP Flowable 需要理解流程歷史、DMP 組織資料與 L5 指標；CFX 與 Doris-SeaTunnel 則涉及 Kafka、來源系統、資料儲存與平台服務。"

# P11
$slide = $pres.Slides.Add(11, 12)
Add-Title $slide "P11｜能力總結" "核心訊息：我的資料工程能力可歸納為四個面向"
$summary = @(
    @("端到端資料交付", "從來源資料到 BI / API / Dashboard"),
    @("批次與串流管線", "Kafka、ODBC、SeaTunnel、Airflow、Cron"),
    @("品質、效能與可靠性", "offset、watermark、retry、backfill、micro-batch"),
    @("跨團隊協作與技術交付", "需求對齊、來源確認、平台建置、資料交付")
)
for ($i = 0; $i -lt 4; $i++) {
    $x = 98 + (($i % 2) * 385)
    $y = 145 + ([math]::Floor($i / 2) * 145)
    Add-Box $slide $summary[$i][0] $x $y 320 48 $colors.Blue $colors.Blue 17 $true $colors.White | Out-Null
    Add-Box $slide $summary[$i][1] $x ($y + 52) 320 54 $colors.White $colors.Border 13 $false $colors.Dark | Out-Null
}
Add-Box $slide "資料工程師能力範圍" 360 248 240 44 $colors.LightGreen $colors.Green 16 $true $colors.Green | Out-Null
Add-Notes $slide "我的能力可以總結為四個面向。我能處理資料管線從接入、處理、儲存、建模到交付的核心工程問題。三個專案共同證明的是能力範圍，而不是三段互不相關的專案經歷。"

# P12
$slide = $pres.Slides.Add(12, 12)
$slide.Background.Fill.ForeColor.RGB = Rgb 247 249 252
Add-Text $slide "P12｜結尾" 44 28 300 34 22 $true $colors.Navy 1 | Out-Null
Add-Text $slide "我不只是將資料搬到資料庫" 90 165 780 42 28 $true $colors.Navy 2 | Out-Null
Add-Text $slide "而是負責建立從資料來源、資料處理、資料治理到資料交付的完整資料供應鏈" 125 225 710 60 22 $false $colors.Dark 2 | Out-Null
$end = @("資料來源", "資料處理", "資料治理", "資料交付")
for ($i = 0; $i -lt $end.Count; $i++) {
    $x = 178 + ($i * 156)
    Add-Box $slide $end[$i] $x 350 112 38 $colors.White $colors.Border 13 $true $colors.Navy | Out-Null
    if ($i -lt $end.Count - 1) { Add-Line $slide ($x + 112) 369 ($x + 154) 369 $colors.Blue 1.7 $true | Out-Null }
}
Add-Notes $slide "結尾回到主軸：我的價值是建立穩定、可追蹤、可重用、可交付的資料供應鏈。CFX 證明我能處理即時製造訊息接入與可靠性；DMP Flowable 證明我能做資料分層、建模、聚合與 BI 語義層；Doris-SeaTunnel POC 證明我能進行資料平台技術選型與可行性驗證。"

# Speaker-only appendix notes are intentionally not added as slides.
$pres.SaveAs($outPath)
$pres.Close()
$ppt.Quit()

[System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null

Write-Host "Created: $outPath"
