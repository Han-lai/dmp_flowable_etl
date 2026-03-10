from fastapi import FastAPI, Query, HTTPException
import clickhouse_connect
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel
from datetime import datetime, timedelta, date
import calendar
import os
import sys
import logging

# 簡易的 Logger 設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("L5_API")

# ClickHouse 連線設定 (直接讀取或設定預設值)
CLICKHOUSE_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', 8121)),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'default')
}

def get_clickhouse_client():
    return clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)

app = FastAPI(
    title="Flowable L5 Insight API",
    description="DMP Flowable L5 任務執行完成率 API 服務 (基於 ClickHouse Gold Layer)",
    version="1.2.0",
    docs_url="/docs",
)

# 定義傳入的資料結構 (Request Schema)
class L5ReportRequest(BaseModel):
    month: str # 格式: yyyy-MM
    vxtype: Optional[str] = "ALL"
    region: Optional[str] = "ALL"
    plant: Optional[str] = "ALL"
    factory: Optional[str] = "ALL"
    line: Optional[str] = "ALL"

# 定義回傳的資料結構
class TaskMetric(BaseModel):
    qty: Union[int, float]
    percentage: str

class ReportRow(BaseModel):
    vxtype: str
    region: str
    plant: str
    factory: str
    line: str
    status: str
    month: TaskMetric
    weeks: Dict[str, TaskMetric]
    days: Dict[str, TaskMetric]

class L5Response(BaseModel):
    status: str
    data: Dict[str, Any]

def get_db():
    """取得 ClickHouse 連線."""
    try:
        client = get_clickhouse_client()
        client.query("SELECT 1")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to ClickHouse: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

def get_date_info(month_str: str):
    """取得月份、週次與日期的清單."""
    try:
        # month_str: "2025-12"
        target_date = datetime.strptime(month_str, "%Y-%m")
        year = target_date.year
        month = target_date.month
        
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)
        
        # 最後 7 天 (倒扣)
        days = []
        for i in range(7):
            days.append((last_day - timedelta(days=i)).strftime("%Y-%m-%d"))
        
        # 最後 3 個 ISO 週次 (W1 of 2026, W52, W51)
        # 由於 ClickHouse 的 toYearWeek(..., 3) 是 ISO 格式，我們在後端處理
        weeks = []
        current_w_date = last_day
        for _ in range(3):
            # ISO Year & Week
            iso_year, iso_week, _ = current_w_date.isocalendar()
            weeks.append(f"W{iso_week}")
            # 跳到上一週同一個星期幾
            current_w_date -= timedelta(days=7)
            
        return {
            "month_label": target_date.strftime("%b."),
            "days": days,
            "weeks": weeks,
            "year": year,
            "month_num": month
        }
    except Exception as e:
        logger.error(f"Error parsing date info: {e}")
        raise ValueError("Invalid month format. Expected yyyy-MM")

@app.get(
    "/api/l5/task-report", 
    response_model=L5Response,
    tags=["L5 指標 API"], 
    summary="L5 任務執行完成率報表 (GET)",
)
async def get_l5_task_report(
    month: str = Query(..., description="月份 (格式: yyyy-MM)", examples=["2025-12"]),
    vxtype: Optional[str] = Query("ALL", description="VX Type"),
    region: Optional[str] = Query("ALL", description="Region"),
    plant: Optional[str] = Query("ALL", description="Plant"),
    factory: Optional[str] = Query("ALL", description="Factory"),
    line: Optional[str] = Query("ALL", description="Line")
):
    return await _generate_l5_report(month, vxtype, region, plant, factory, line)

@app.post(
    "/api/l5/task-report", 
    response_model=L5Response,
    tags=["L5 指標 API"], 
    summary="L5 任務執行完成率報表 (POST)",
    description="傳入 JSON Body 進行查詢，適合複雜過濾。"
)
async def post_l5_task_report(request: L5ReportRequest):
    """
    透過 POST 傳入 JSON 資料進行查詢。
    """
    return await _generate_l5_report(
        request.month, 
        request.vxtype, 
        request.region, 
        request.plant, 
        request.factory, 
        request.line
    )

async def _generate_l5_report(month, vxtype="ALL", region="ALL", plant="ALL", factory="ALL", line="ALL"):
    """
    核心報表生成邏輯 (共享於 GET 與 POST).
    """
    try:
        # 1. 準備時間緯度
        date_info = get_date_info(month)
        
        # 2. 準備 過濾條件
        filters = []
        if vxtype != "ALL": filters.append(f"vx_type = '{vxtype}'")
        if region != "ALL": filters.append(f"region = '{region}'")
        if plant != "ALL": filters.append(f"plant = '{plant}'")
        if factory != "ALL": filters.append(f"factory = '{factory}'")
        if line != "ALL": filters.append(f"line = '{line}'")
        
        where_clause = " AND ".join(filters) if filters else "1=1"
        
        # 3. 組合 SQL
        days_str = ", ".join([f"'{d}'" for d in date_info['days']])
        
        query = f"""
            SELECT
                'Monthly' as period_type,
                'Total' as label,
                sum(total_task) as total,
                sum(todo_count) as todo,
                sum(doing_count) as doing,
                sum(done_count) as done,
                max(acc_todo_doing) as acc
            FROM gold.rmv_l5_task_completion
            WHERE {where_clause} AND toStartOfMonth(snapshot_date) = '{month}-01'
            
            UNION ALL
            
            SELECT
                'Daily' as period_type,
                toString(snapshot_date) as label,
                sum(total_task) as total,
                sum(todo_count) as todo,
                sum(doing_count) as doing,
                sum(done_count) as done,
                max(acc_todo_doing) as acc
            FROM gold.rmv_l5_task_completion
            WHERE {where_clause} AND snapshot_date IN ({days_str})
            GROUP BY snapshot_date
            
            UNION ALL
            
            SELECT
                'Weekly' as period_type,
                concat('W', toString(toWeek(snapshot_date, 3))) as label,
                sum(total_task) as total,
                sum(todo_count) as todo,
                sum(doing_count) as doing,
                sum(done_count) as done,
                max(acc_todo_doing) as acc
            FROM gold.rmv_l5_task_completion
            WHERE {where_clause} 
              AND snapshot_date >= subtractDays(toDate('{month}-01'), 30)
              AND snapshot_date <= addDays(toDate('{month}-01'), 40)
              AND label IN ({", ".join([f"'{w}'" for w in date_info['weeks']])})
            GROUP BY label
        """
        
        logger.info(f"Executing L5 Query: {query}")
        client = get_db()
        result = client.query(query)
        
        # 4. 資料後處理
        raw_data = {}
        for row in result.result_rows:
            p_type, label, total, todo, doing, done, acc = row
            if p_type not in raw_data: raw_data[p_type] = {}
            raw_data[p_type][label] = {
                "Total Task": total,
                "Todo": todo,
                "Doing": doing,
                "Done": done,
                "Doing+Done": doing + done,
                "Todo+Doing(Acc)": acc
            }

        # 5. 格式化輸出
        statuses = ["Total Task", "Todo", "Doing", "Done", "Doing+Done", "Todo+Doing(Acc)"]
        table_rows = []
        
        for status in statuses:
            month_qty = raw_data.get("Monthly", {}).get("Total", {}).get(status, 0)
            month_total = raw_data.get("Monthly", {}).get("Total", {}).get("Total Task", 0)
            
            week_metrics = {}
            for w in date_info['weeks']:
                qty = raw_data.get("Weekly", {}).get(w, {}).get(status, 0)
                tot = raw_data.get("Weekly", {}).get(w, {}).get("Total Task", 0)
                pct = f"{round(qty * 100 / tot, 1)}%" if tot > 0 and status != "Total Task" else "-"
                week_metrics[w] = {"qty": qty, "percentage": pct}

            day_metrics = {}
            for d in date_info['days']:
                qty = raw_data.get("Daily", {}).get(d, {}).get(status, 0)
                tot = raw_data.get("Daily", {}).get(d, {}).get("Total Task", 0)
                pct = f"{round(qty * 100 / tot, 1)}%" if tot > 0 and status != "Total Task" else "-"
                day_metrics[d] = {"qty": qty, "percentage": pct}

            month_pct = f"{round(month_qty * 100 / month_total, 1)}%" if month_total > 0 and status != "Total Task" else "-"

            table_rows.append({
                "vxtype": vxtype,
                "region": region,
                "plant": plant,
                "factory": factory,
                "line": line,
                "status": status,
                "month": {"qty": month_qty, "percentage": month_pct},
                "weeks": week_metrics,
                "days": day_metrics
            })

        return {
            "status": "success",
            "data": {
                "month": month,
                "columns": {
                    "month": date_info['month_label'],
                    "weeks": date_info['weeks'],
                    "days": date_info['days']
                },
                "rows": table_rows
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
