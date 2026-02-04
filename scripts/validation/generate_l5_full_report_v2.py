import clickhouse_connect
import pandas as pd
import argparse
from datetime import datetime, timedelta

def get_iso_week(date_obj):
    # Returns (year, week_num)
    return date_obj.isocalendar()[0], date_obj.isocalendar()[1]

def get_week_range(year, week):
    # Returns (monday, sunday)
    d = datetime.strptime(f'{year}-W{week:02}-1', "%G-W%V-%u")
    return d.date(), (d + timedelta(days=6)).date()

def generate_report(year_month, filters=None, output_file='l5_report_output.md'):
    """
    依據 03_1_columns_defin.md 規格生成報表。
    :param year_month: 查詢月份 'YYYY-MM'
    :param filters: 篩選條件 e.g. {'region': 'CNE'}
    """
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    # 1. 決定基準日 (Reference Date) 與 查詢月份範圍
    query_dt = datetime.strptime(year_month, "%Y-%m")
    today = datetime.now()
    
    # 查詢月份的最後一天
    next_m = (query_dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_day_of_month = (next_m - timedelta(days=1)).date()
    first_day_of_month = query_dt.date()
    
    # 基準日 (用於 Dn 推算)
    # 若查詢月份是當前月份，基準日為 Today
    # 若是歷史月份，基準日為 該月最後一天的隔天 (使得 Dn-1 為最後一天)
    if query_dt.year == today.year and query_dt.month == today.month:
        base_date = today.date()
    else:
        base_date = last_day_of_month + timedelta(days=1)
    
    # 2. 定義所有時間週期 (依照規格順序)
    periods = []
    
    # (1) Total: 全歷史
    periods.append({'label': 'Total', 'start': '1970-01-01', 'end': '2099-12-31', 'is_acc_rolling': False})
    
    # (2) Month: 自然月
    periods.append({'label': query_dt.strftime('%b'), 'start': first_day_of_month, 'end': last_day_of_month, 'is_acc_rolling': False})
    
    # (3) Weekly: Wx, Wx-1, Wx-2
    # x 的計算
    if query_dt.year == today.year and query_dt.month == today.month:
        target_dt = today
    else:
        target_dt = datetime.combine(last_day_of_month, datetime.min.time())
    
    y, w = get_iso_week(target_dt)
    for i in range(3):
        # 標籤 Wx, Wx-1, Wx-2
        # 注意：ISO 週次跨年時標籤需正確顯示
        # 這裡簡化顯示標籤為 W{x}
        curr_y, curr_w = get_iso_week(target_dt - timedelta(weeks=i))
        monday, sunday = get_week_range(curr_y, curr_w)
        
        # 規格：若該週尚未結束，僅統計目前已發生日期
        effective_end = min(sunday, today.date())
        
        periods.append({
            'label': f'W{curr_w}', 
            'start': monday, 
            'end': effective_end,
            'is_acc_rolling': False # 週別 ACC 定義為該週內
        })
        
    # (4) Daily: Dn-1 ~ Dn-7
    for i in range(1, 8):
        d = base_date - timedelta(days=i)
        periods.append({
            'label': d.strftime('%m/%d'), 
            'start': d, 
            'end': d,
            'is_acc_rolling': True # 規格：日級別為 Rolling 7 Days
        })

    # 3. 執行計算
    if not filters:
        filter_sql = "1=1"
        dim_select = "'ALL' as vx_type, 'ALL' as region, 'ALL' as plant, 'ALL' as factory, 'ALL' as line"
    else:
        filter_parts = [f"{k} = '{v}'" for k, v in filters.items()]
        filter_sql = " AND ".join(filter_parts)
        dim_select = "vx_type, region, plant, factory, line"

    status_list = ["Total Task", "Todo", "Doing", "Done", "Doing+Done", "Todo+Doing(Acc)"]
    report_data = {}

    for p in periods:
        label = p['label']
        p_start = p['start']
        p_end = p['end']
        
        # Snapshot SQL: 針對 Snapshot 指標 (Total, Todo, Doing, Done)
        if p_start == p_end:
            # 日報表：採計該日「新啟動」的任務
            snap_sql = f"""
            SELECT {dim_select}, 
                   count() as total,
                   countIf(current_status = 'TODO') as todo,
                   countIf(current_status = 'DOING') as doing,
                   countIf(current_status = 'DONE') as done
            FROM (
                SELECT {dim_select}, task_id,
                       multiIf(task_end_date = '{p_start}', 'DONE',
                               task_claim_date = '{p_start}', 'DOING', 'TODO') as current_status
                FROM silver.mv_fact_task_vx FINAL
                WHERE is_excluded = 0 
                  AND task_start_date = '{p_start}'
                  AND {filter_sql}
                GROUP BY {dim_select}, task_id, task_end_date, task_claim_date
            )
            GROUP BY vx_type, region, plant, factory, line
            """
        else:
            # 週與月報表：採計該期間內「新啟動」的任務並取最晚狀態
            snap_sql = f"""
            SELECT {dim_select}, 
                   count() as total,
                   countIf(final_status = 'TODO') as todo,
                   countIf(final_status = 'DOING') as doing,
                   countIf(final_status = 'DONE') as done
            FROM (
                SELECT {dim_select}, task_id,
                       argMax(task_status, multiIf(task_status='DONE', 3, task_status='DOING', 2, 1)) as final_status
                FROM silver.mv_fact_task_vx FINAL
                WHERE is_excluded = 0 
                  AND task_start_date BETWEEN '{p_start}' AND '{p_end}'
                  AND {filter_sql}
                GROUP BY {dim_select}, task_id
            )
            GROUP BY vx_type, region, plant, factory, line
            """
        df_snap = client.query_df(snap_sql)

        # ACC SQL: 
        # 若是 is_acc_rolling (Daily), 區間為 [D-6, D]
        # 且依照 PR1 範例，只有在該區間內「開始」的任務才計入 Acc (Rolling 7 Days Expiry)
        acc_start = (p_end - timedelta(days=6)) if p.get('is_acc_rolling') else p_start
        acc_start_filter = acc_start if p.get('is_acc_rolling') else datetime.strptime("1970-01-01", "%Y-%m-%d").date()
        acc_sql = f"""
        SELECT {dim_select}, count(DISTINCT task_id) as acc
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 
          AND task_start_date BETWEEN '{acc_start}' AND '{p_end}'
          AND (task_end_date > '{p_end}' OR task_end_date IS NULL) 
          AND {filter_sql}
        GROUP BY vx_type, region, plant, factory, line
        """
        df_acc = client.query_df(acc_sql)

        # 合併維度，確保 Snapshot 為空但 Acc 有值時也能顯示
        all_dims = set()
        if not df_snap.empty:
            for _, r in df_snap.iterrows():
                all_dims.add((r['vx_type'], r['region'], r['plant'], r['factory'], r['line']))
        if not df_acc.empty:
            for _, r in df_acc.iterrows():
                all_dims.add((r['vx_type'], r['region'], r['plant'], r['factory'], r['line']))
        
        if not all_dims and filters:
            # 至少補一個指定的 Filter Row
            all_dims.add((filters.get('vx_type', 'ALL'), filters.get('region', 'ALL'), 
                          filters.get('plant', 'ALL'), filters.get('factory', 'ALL'), filters.get('line', 'ALL')))

        for dims in all_dims:
            # 取得該維度的 Snapshot 值
            snap_match = df_snap[(df_snap['vx_type']==dims[0]) & (df_snap['region']==dims[1]) & 
                                 (df_snap['plant']==dims[2]) & (df_snap['factory']==dims[3]) & 
                                 (df_snap['line']==dims[4])] if not df_snap.empty else pd.DataFrame()
            
            total = snap_match.iloc[0]['total'] if not snap_match.empty else 0
            todo = snap_match.iloc[0]['todo'] if not snap_match.empty else 0
            doing = snap_match.iloc[0]['doing'] if not snap_match.empty else 0
            done = snap_match.iloc[0]['done'] if not snap_match.empty else 0
            
            # 取得該維度的 Acc 值
            acc_val = 0
            if not df_acc.empty:
                acc_match = df_acc[(df_acc['vx_type']==dims[0]) & (df_acc['region']==dims[1]) & 
                                   (df_acc['plant']==dims[2]) & (df_acc['factory']==dims[3]) & 
                                   (df_acc['line']==dims[4])]
                if not acc_match.empty: acc_val = acc_match.iloc[0]['acc']

            vals = {"Total Task": total, "Todo": todo, "Doing": doing, "Done": done, 
                    "Doing+Done": doing+done, "Todo+Doing(Acc)": acc_val}

            for s in status_list:
                qty = vals[s]
                # 注意：目前規格中 Dn (%) 是佔 Total Task 比例，若 Total Task 為 0 則顯示 0
                pct = (qty / total * 100) if total > 0 else 0
                key = dims + (s,)
                if key not in report_data: report_data[key] = {}
                report_data[key][label] = (qty, pct)

    # 4. 構建 Markdown
    header_labels = [p['label'] for p in periods]
    cols = ["Vx", "Region", "Plant", "Factory", "Line", "Status"]
    md = "| " + " | ".join(cols) + " | " + " | ".join([f"{l} Qty | {l} (%)" for l in header_labels]) + " |\n"
    md += "| --- " * (len(cols) + len(header_labels)*2) + "|\n"

    s_order = {s: i for i, s in enumerate(status_list)}
    sorted_keys = sorted(report_data.keys(), key=lambda x: (x[0], x[1], x[2], x[3], x[4], s_order[x[5]]))

    for k in sorted_keys:
        row_str = "| " + " | ".join(k) + " | "
        for l in header_labels:
            q, p = report_data[k].get(l, (0, 0))
            row_str += f"{int(q):,} | {p:.1f}% | "
        md += row_str + "\n"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"完成！基準月: {year_month}, 基準日: {base_date}, 報表已存至 {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate L5 Task Status Comparison Report")
    parser.add_argument("--month", type=str, default="2025-12", help="Target month (YYYY-MM)")
    parser.add_argument("--all", action="store_true", help="Generate global report (unfiltered)")
    parser.add_argument("--region", type=str, help="Filter by region")
    parser.add_argument("--plant", type=str, help="Filter by plant")
    parser.add_argument("--factory", type=str, help="Filter by factory")
    parser.add_argument("--line", type=str, help="Filter by line")
    parser.add_argument("--out", type=str, default="l5_report_output.md", help="Output file name")

    args = parser.parse_args()

    # Build filters dictionary
    filters = {}
    if not args.all:
        if args.region: filters['region'] = args.region
        if args.plant: filters['plant'] = args.plant
        if args.factory: filters['factory'] = args.factory
        if args.line: filters['line'] = args.line
        
        # If no specific filters and not --all, default to the previous E5 example
        if not filters:
            filters = {'region': 'CNE', 'plant': 'WJ2', 'factory': 'NBU', 'line': 'E5'}
    else:
        filters = None # Global mode

    generate_report(args.month, filters=filters, output_file=args.out)
