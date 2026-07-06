# CLAUDE.md — DMP Flowable（AI Session 入口）

> 本檔取代 2026-07-03 前的舊版 claude.md（舊版引用已不存在的腳本，已刪除）。
> 完整 AI 知識庫: **[docs/08_ai_agent/00_INDEX.md](docs/08_ai_agent/00_INDEX.md)**（先讀）。
> 即時專案狀態: **[memory-bank/activeContext.md](memory-bank/activeContext.md)**。

## 專案一句話

MSSQL（Flowable BPM 生產庫）→ ODBC → ClickHouse 三層數倉（bronze/silver/gold）→ Cube.js/FastAPI，產出 L5 任務完成率等製造 KPI。生產運作中，每日 00:00 自動排程。

## 🔴 鐵律（違反=事故）

1. **MSSQL 來源庫唯讀**——嚴禁任何寫入/DDL。
2. **絕不自動 git push**——commit 後停下等使用者說「推送」。
3. **GitHub（origin）push 前**：diff 不得含 IP/密碼；作者身份必須 `Han-lai <sh41bee@gmail.com>`（公司身份只用於 GitLab）。⚠ **本地 master 歷史與 GitHub 乾淨歷史完全分叉（本地歷史層仍含舊機敏字串）——嚴禁直接 push/force-push master 到 GitHub**，必須從 origin/master 建分支 cherry-pick（詳見 [Assessment R1](docs/08_ai_agent/01_Project_Assessment.md)）。
4. **連線資訊一律環境變數**（`infra/.env`，不進版控），程式碼不寫死 IP/密碼。
5. `--reset` / TRUNCATE / DROP / `ALTER DELETE` 先向使用者確認。
6. 跑 sync 前確認 `MSSQL_PASSWORD` 已設——空字串會把 15 張維度表清空（2026-06 事故）。

## 核心結構（誰負責什麼）

```
scripts/etl/sync_unified_odbc.py   MSSQL→Bronze（19 表，讀 config/sync_tables.yaml）
scripts/etl/execute_etl.py         Silver/Gold 運算（讀 config/pipeline_config.yaml，8 phases）
scripts/etl/setup_schema.py        DDL 部署（讀 config/infra_config.yaml）
sql/etl/dml/*.sql                  ★ 全部業務規則在這（vx_type/排除/Cohort/ACC）
cube/model/cubes/                  Cube.js 語意層（只讀 gold.rmv_l5_task_summary FINAL）
api/main.py                        FastAPI L5 報表（port 7088）
infra/                             docker-compose（cube 4002 / grafana 9003 / prometheus 9011）
memory-bank/                       AI 工作記憶（activeContext=當前狀態）
docs/08_ai_agent/                  ★ AI 知識庫（模組地圖/術語/踩坑錄/工作流程）
```

## 常用指令

```bash
python scripts/etl/execute_etl.py --status                 # 生產健康儀表板（水位線/checkpoint/筆數）
python scripts/etl/sync_unified_odbc.py --table all        # 手動 Bronze 同步
python scripts/etl/execute_etl.py --daily --low-ram        # 每日增量（自動接龍）
python scripts/etl/execute_etl.py --backfill --start 2026-06-01 --end 2026-06-30 --low-ram  # 回填
python -m pytest tests/ -v                                 # 單元測試
```

## 關鍵事實速記

- 所有表都是 **ReplacingMergeTree 物理表**（`mv_`/`rmv_` 前綴是歷史命名，不是 MV）；查詢端讀 summary 要 `FINAL`。
- Gold summary **雙管線**：`<2026-04-01` 走 historical（V3）、`≥2026-04-01` 走 V4，邊界硬編碼在兩支 SQL。
- 費率一律 `floor(qty*100/total)` 整數百分比（Rule 2），禁 round()。
- CH LEFT JOIN 失敗回 `''` 不是 NULL → 用 `NULLIF(x,'')` 再 COALESCE。
- JOIN ReplacingMergeTree 用 `argMax(col, _refresh_time)` 防列數翻倍。
- 文件與程式碼衝突時**以程式碼為準**，順手修文件；已知失真清單見 [Assessment §6](docs/08_ai_agent/01_Project_Assessment.md)。
- Commit 訊息用英文 conventional commits。

## 遇到問題

先搜 [docs/08_ai_agent/05_Troubleshooting.md](docs/08_ai_agent/05_Troubleshooting.md)（全部歷史事故根因），再搜 memory-bank/progress.md。
