import clickhouse_connect
import pandas as pd
import argparse
from datetime import datetime, timedelta

def generate_report(filters=None, months=None, weeks=None, days=None, output_file='l5_report_output.md'):
    """
    生成 L5 任務狀態對比報表。
    :param filters: 字典形式的篩選條件, e.g. {'region': 'CNE', 'plant': 'WJ2'}
    :param months: 列表形式的月份, e.g. ['2025-12']
    :param weeks: 列表形式的週次定義, 每項為 (label, start, end), e.g. [('W52', '2025-12-22', '2025-12-28')]
    :param days: 列表形式的日期, e.g. ['2025-12-31', '2025-12-30']
    """
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

    # 1. 處理維度篩選
    if not filters:
        filter_sql = "1=1"
        dim_select = "'ALL' as vx_type, 'ALL' as region, 'ALL' as plant, 'ALL' as factory, 'ALL' as line"
        print("--- 模式: ALL (不分條件) ---")
    else:
        filter_parts = [f"{k} = '{v}'" for k, v in filters.items()]
        filter_sql = " AND ".join(filter_parts)
        # 如果使用者指定了特定維度，SQL Select 需保留這些維度以供 Group By
        dim_select = "vx_type, region, plant, factory, line"
        print(f"--- 模式: 篩選條件 {filter_sql} ---")

    # 2. 定義時間週期
    periods = []
    if months:
        for m in months:
            # 簡化處理：假設為 YYYY-MM 格式，取該月第一天到最後一天
            start = f"{m}-01"
            dt = datetime.strptime(start, "%Y-%m-%d")
            next_m = (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = (next_m - timedelta(days=1)).strftime("%Y-%m-%d")
            periods.append({'label': dt.strftime('%b'), 'start': start, 'end': end})
    
    if weeks:
        for label, s, e in weeks:
            periods.append({'label': label, 'start': s, 'end': e})
            
    if days:
        for d in days:
            periods.append({'label': d, 'start': d, 'end': d})

    if not periods:
        print("錯誤: 未指定任何時間週期。")
        return

    # 3. 執行計算
    status_list = ["Total Task", "Todo", "Doing", "Done", "Doing+Done", "Todo+Doing(Acc)"]
    report_data = {}

    for p in periods:
        label = p['label']
        p_start = p['start']
        p_end = p['end']

        # Snapshot SQL
        snap_sql = f"""
        SELECT {dim_select}, sum(total_task) as total, sum(todo_count) as todo,
               sum(doing_count) as doing, sum(done_count) as done
        FROM gold.rmv_l5_task_completion
        WHERE snapshot_date BETWEEN '{p_start}' AND '{p_end}' AND {filter_sql}
        GROUP BY {dim_select.replace(' as vx_type', '').replace(' as region', '').replace(' as plant', '').replace(' as factory', '').replace(' as line', '')}
        """
        df_snap = client.query_df(snap_sql)

        # ACC SQL
        acc_sql = f"""
        SELECT {dim_select}, count(DISTINCT task_id) as acc
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND task_start_date <= '{p_end}'
          AND (task_end_date >= '{p_start}' OR task_end_date IS NULL) AND {filter_sql}
        GROUP BY {dim_select.replace(' as vx_type', '').replace(' as region', '').replace(' as plant', '').replace(' as factory', '').replace(' as line', '')}
        """
        df_acc = client.query_df(acc_sql)

        if df_snap.empty: continue

        for _, row in df_snap.iterrows():
            dims = (row['vx_type'], row['region'], row['plant'], row['factory'], row['line'])
            total, todo, doing, done = row['total'], row['todo'], row['doing'], row['done']
            
            acc_val = 0
            if not df_acc.empty:
                m = df_acc[(df_acc['vx_type']==row['vx_type']) & (df_acc['region']==row['region'])] # 簡化比對
                if not m.empty: acc_val = m.iloc[0]['acc']

            vals = {"Total Task": total, "Todo": todo, "Doing": doing, "Done": done, 
                    "Doing+Done": doing+done, "Todo+Doing(Acc)": acc_val}

            for s in status_list:
                qty = vals[s]
                pct = (qty / total * 100) if total > 0 else 0
                key = dims + (s,)
                if key not in report_data: report_data[key] = {}
                report_data[key][label] = (qty, pct)

    # 4. 構建表格
    header_labels = [p['label'] for p in periods]
    md = "| Vx | Region | Plant | Factory | Line | Status | " + " | ".join([f"{l} Qty | {l} (%)" for l in header_labels]) + " |\n"
    md += "| --- " * (6 + len(header_labels)*2) + "|\n"

    s_order = {s: i for i, s in enumerate(status_list)}
    sorted_keys = sorted(report_data.keys(), key=lambda x: (x[0], x[1], x[2], x[3], x[4], s_order[x[5]]))

    for k in sorted_keys:
        row = "| " + " | ".join(k) + " | "
        for l in header_labels:
            q, p = report_data[k].get(l, (0, 0))
            row += f"{int(q):,} | {p:.1f}% | "
        md += row + "\n"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"完成！報表已存至 {output_file}")

if __name__ == "__main__":
    # 若要執行「全維度 (ALL)」且是 12 月份的資料，請依照以下參數調整：
    generate_report(
        filters=None,           # 設定為 None 代表「全維度 (ALL)」
        months=['2025-12'],     # 12 月份月報
        weeks=[                 # 12 月份內包含的週次
            ('W1', '2025-12-29', '2025-12-31'), 
            ('W52', '2025-12-22', '2025-12-28'), 
            ('W51', '2025-12-15', '2025-12-21')
        ],
        days=[f"2025-12-{d:02d}" for d in range(31, 24, -1)], # 12/31 至 12/25 的日報
        output_file='l5_report_all_dec.md'                   # 為了區分，輸出檔名可自訂
    )
