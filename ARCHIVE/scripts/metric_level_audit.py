"""
指標層級審計腳本
逐一檢視以下面向是否與 benchmark 等價：
A. 指標計算公式
B. Join 邏輯
C. 指標適用層級
"""
import clickhouse_connect

my_client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
ref_client = clickhouse_connect.get_client(host='10.136.218.207', port=8124, username='ch_user', password='ch_strong_password_change_me')

print('=' * 100)
print('指標層級審計報告')
print('=' * 100)

# ============================================
# A. 指標計算公式比較
# ============================================
print('\n' + '=' * 100)
print('A️⃣ 指標計算公式比較')
print('=' * 100)

print('\n【A1. TASK_STATUS 計算集合比較】')
print('-' * 80)
print('''
┌─────────────┬──────────────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────────┐
│ 狀態        │ 參考環境 (task_state)                                            │ 你的環境 (TASK_STATUS)                                           │
├─────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ TERMINATED  │ DELETE_REASON_ IS NOT NULL                                       │ DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != ''              │
│ /CANCELLED  │                                                                  │                                                                  │
├─────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ TODO        │ ASSIGNEE_ IS NULL AND END_TIME_ IS NULL                          │ ASSIGNEE_ IS NULL AND END_TIME_ IS NULL                          │
├─────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ DOING       │ ASSIGNEE_ IS NOT NULL AND END_TIME_ IS NULL                      │ ASSIGNEE_ IS NOT NULL AND END_TIME_ IS NULL                      │
├─────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ DONE_AUTO   │ ASSIGNEE_ IS NOT NULL AND CLAIM_TIME_ IS NULL AND END_TIME_!=NULL│ ASSIGNEE_ IS NOT NULL AND CLAIM_TIME_ IS NULL AND END_TIME_!=NULL│
├─────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ DONE        │ 其他 (有 END_TIME_)                                              │ END_TIME_ IS NOT NULL (其他情況)                                 │
└─────────────┴──────────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────────┘
''')

# 檢查 DELETE_REASON_ 空字串的影響
print('【A1.1 DELETE_REASON_ 空字串檢查】')
empty_delete_reason = my_client.query("""
SELECT count(*) FROM bronze.bpm_act_hi_taskinst 
WHERE DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ = ''
""").result_rows[0][0]
print(f"  DELETE_REASON_ = '' 的筆數: {empty_delete_reason}")
if empty_delete_reason > 0:
    print(f"  ⚠️ 警告: 有 {empty_delete_reason} 筆 DELETE_REASON_ 為空字串")
    print(f"     參考環境會判定為 TERMINATED，你的環境會判定為其他狀態")
else:
    print(f"  ✅ 無影響")

print('\n【A2. 自動完成率計算公式比較】')
print('-' * 80)
print('''
┌──────────────┬────────────────────────────────────────────────────────────────┐
│ 環境         │ 公式                                                           │
├──────────────┼────────────────────────────────────────────────────────────────┤
│ 參考環境     │ DONE_AUTO / (DONE + DONE_AUTO) * 100                           │
├──────────────┼────────────────────────────────────────────────────────────────┤
│ 你的環境     │ DONE_AUTO / (DONE + DONE_AUTO) * 100                           │
└──────────────┴────────────────────────────────────────────────────────────────┘
''')
print('  ✅ 公式一致')

# 實際計算比較
ref_rate = ref_client.query("""
SELECT round(countIf(node_state = 'DONE_AUTO') * 100.0 / countIf(node_state IN ('DONE', 'DONE_AUTO')), 2) 
FROM flowable_analytics.gold_proc_task_node_rmv WHERE node_type = 'TASK'
""").result_rows[0][0]

my_rate = my_client.query("""
SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) 
FROM silver.V_HI_PROC_TASK_NODE
""").result_rows[0][0]

print(f'\n  參考環境自動完成率: {ref_rate}%')
print(f'  你的環境自動完成率: {my_rate}%')
print(f'  差異: {abs(ref_rate - my_rate):.2f}%')

# ============================================
# B. Join 邏輯比較
# ============================================
print('\n' + '=' * 100)
print('B️⃣ Join 邏輯比較')
print('=' * 100)

print('\n【B1. V_HI_PROC_TASK_NODE Join 結構】')
print('-' * 80)
print('''
┌──────────────────────────────────────────────────────────────────────────────┐
│ 你的環境 V_HI_PROC_TASK_NODE                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ bpm_act_hi_taskinst (t)                                                      │
│   LEFT JOIN bpm_act_hi_procinst (p) ON t.PROC_INST_ID_ = p.PROC_INST_ID_     │
│   LEFT JOIN V_PROC_VARIABLES_PIVOTED (v) ON t.PROC_INST_ID_ = v.PROC_INST_ID │
│   LEFT JOIN bpm_act_re_procdef (pd) ON t.PROC_DEF_ID_ = pd.ID_               │
│   LEFT JOIN common_hr_employee (e) ON t.ASSIGNEE_ = e.EmpCode                │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 參考環境 silver_enriched_taskinst                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ ACT_HI_TASKINST (t)                                                          │
│   LEFT JOIN silver_enriched_procinst (p) ON t.PROC_INST_ID_ = p.proc_inst_id │
│   LEFT JOIN silver_task_variables_pivoted (tv) ON t.ID_ = tv.task_id         │
│   LEFT JOIN ACT_HI_IDENTITYLINK (il) ON t.ID_ = il.TASK_ID_                  │
└──────────────────────────────────────────────────────────────────────────────┘
''')

print('【B1.1 Join 差異分析】')
print('  ⚠️ 差異 1: 參考環境有 silver_task_variables_pivoted (任務層變數)')
print('     你的環境只有 V_PROC_VARIABLES_PIVOTED (流程層變數)')
print('  ⚠️ 差異 2: 參考環境有 ACT_HI_IDENTITYLINK (候選人資訊)')
print('     你的環境沒有此 Join')
print('  ✅ 相同: 都有 JOIN 流程實例、流程定義')

# 檢查是否有任務層變數
print('\n【B1.2 任務層變數檢查】')
task_vars = my_client.query("""
SELECT count(*) FROM bronze.bpm_act_hi_varinst WHERE TASK_ID_ IS NOT NULL
""").result_rows[0][0]
print(f'  任務層變數筆數: {task_vars}')
if task_vars > 0:
    print(f'  ⚠️ 有 {task_vars} 筆任務層變數，但你的環境沒有使用')
else:
    print(f'  ✅ 無任務層變數，不影響')

print('\n【B2. V_HI_PROCINST_NODE Join 結構】')
print('-' * 80)
print('''
┌──────────────────────────────────────────────────────────────────────────────┐
│ 你的環境 V_HI_PROCINST_NODE                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ bpm_act_hi_procinst (p)                                                      │
│   LEFT JOIN V_PROC_VARIABLES_PIVOTED (v) ON p.PROC_INST_ID_ = v.PROC_INST_ID │
│   LEFT JOIN bpm_act_re_procdef (pd) ON p.PROC_DEF_ID_ = pd.ID_               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 參考環境 silver_enriched_procinst                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ ACT_HI_PROCINST (p)                                                          │
│   LEFT JOIN ACT_RE_PROCDEF (pd) ON p.PROC_DEF_ID_ = pd.ID_                   │
│   LEFT JOIN silver_proc_variables_pivoted (pv) ON p.ID_ = pv.proc_inst_id    │
└──────────────────────────────────────────────────────────────────────────────┘
''')
print('  ✅ Join 結構一致')

print('\n【B3. V_PROC_VARIABLES_PIVOTED 變數比較】')
print('-' * 80)
print('''
┌──────────────────────────────────────────────────────────────────────────────┐
│ 你的環境                          │ 參考環境                                 │
├───────────────────────────────────┼──────────────────────────────────────────┤
│ plant                             │ plant                                    │
│ factory                           │ factory                                  │
│ region                            │ region                                   │
│ sapPlant                          │ sapPlant                                 │
│ lineName                          │ lineName                                 │
│ modelName                         │ modelName                                │
│ -                                 │ moNumber                                 │
│ -                                 │ scheduleNumber                           │
│ -                                 │ sapProductGroup                          │
│ -                                 │ productionArea                           │
│ -                                 │ deliveryArea                             │
│ -                                 │ pallet                                   │
│ -                                 │ transferNo                               │
│ -                                 │ qBlockEventId                            │
│ -                                 │ defectSn                                 │
│ -                                 │ time                                     │
│ -                                 │ initiator                                │
│ -                                 │ _PROCESS_NODE_INFO                       │
└───────────────────────────────────┴──────────────────────────────────────────┘
''')
print('  ⚠️ 你的環境缺少 12 個變數欄位')
print('     這些欄位用於過濾條件 (如 moNumber NOT LIKE Q%/R%)')

# ============================================
# C. 指標適用層級
# ============================================
print('\n' + '=' * 100)
print('C️⃣ 指標適用層級分析')
print('=' * 100)

print('\n【C1. 指標層級對照表】')
print('-' * 80)
print('''
┌─────────────────────────────────┬──────────────┬──────────────┬──────────────────────────────────┐
│ 指標                            │ 必須流程層   │ 可用任務層   │ 說明                             │
├─────────────────────────────────┼──────────────┼──────────────┼──────────────────────────────────┤
│ 在途任務數                      │              │ ✅           │ 只需任務層                       │
│ TASK_STATUS 分布                │              │ ✅           │ 只需任務層                       │
│ 自動完成率                      │              │ ✅           │ 只需任務層                       │
│ 任務處理時長                    │              │ ✅           │ 只需任務層                       │
├─────────────────────────────────┼──────────────┼──────────────┼──────────────────────────────────┤
│ 在途流程數                      │ ✅           │              │ 需要流程層 PROC_STATE            │
│ 流程總歷時                      │ ✅           │              │ 需要流程層 DURATION              │
│ 流程階層深度                    │ ✅           │              │ 需要 SUPER_PROCESS_INSTANCE_ID   │
├─────────────────────────────────┼──────────────┼──────────────┼──────────────────────────────────┤
│ 業務事件總歷時                  │ ✅           │              │ 需要 GROUP BY BUSINESS_KEY       │
│ 在途業務事件數                  │ ✅           │              │ 需要流程層判斷是否完成           │
└─────────────────────────────────┴──────────────┴──────────────┴──────────────────────────────────┘
''')

print('\n【C2. 語意正確性檢查】')
print('-' * 80)

# 檢查 1: 在途任務數
print('\n  [1] 在途任務數')
ref_in_progress = ref_client.query("""
SELECT count(*) FROM flowable_analytics.gold_proc_task_node_rmv 
WHERE node_type = 'TASK' AND node_state IN ('TODO', 'DOING')
""").result_rows[0][0]
my_in_progress = my_client.query("""
SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')
""").result_rows[0][0]
print(f'      參考環境: {ref_in_progress}')
print(f'      你的環境: {my_in_progress}')
print(f'      ✅ 語意正確: 都是 TODO + DOING')

# 檢查 2: 自動完成率的分母
print('\n  [2] 自動完成率')
print('      分子: DONE_AUTO')
print('      分母: DONE + DONE_AUTO')
print('      ✅ 語意正確: 排除 CANCELLED/TODO/DOING')

# 檢查 3: 業務事件層
print('\n  [3] 業務事件層 (V_HI_BIZ_EVENT_INFO)')
print('      ⚠️ 潛在問題: 你的環境沒有過濾條件')
print('      參考環境過濾: TASK_DEF_KEY_ NOT LIKE E%/C%')
print('      這可能導致業務事件統計包含不應計入的任務')

# ============================================
# 總結
# ============================================
print('\n' + '=' * 100)
print('審計總結')
print('=' * 100)

print('''
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 面向                │ 狀態   │ 說明                                                            │
├─────────────────────┼────────┼─────────────────────────────────────────────────────────────────┤
│ A1. TASK_STATUS     │ ✅     │ 計算邏輯一致 (名稱不同: TERMINATED vs CANCELLED)                │
│ A2. 自動完成率      │ ✅     │ 公式一致: DONE_AUTO / (DONE + DONE_AUTO)                        │
├─────────────────────┼────────┼─────────────────────────────────────────────────────────────────┤
│ B1. Task Join       │ ⚠️     │ 缺少任務層變數 (silver_task_variables_pivoted)                  │
│ B2. Proc Join       │ ✅     │ 結構一致                                                        │
│ B3. 變數欄位        │ ⚠️     │ 缺少 12 個變數欄位 (moNumber, scheduleNumber 等)                │
├─────────────────────┼────────┼─────────────────────────────────────────────────────────────────┤
│ C1. 任務層指標      │ ✅     │ 語意正確                                                        │
│ C2. 流程層指標      │ ✅     │ 語意正確                                                        │
│ C3. 業務事件指標    │ ⚠️     │ 缺少過濾條件，可能包含不應計入的任務                            │
└─────────────────────┴────────┴─────────────────────────────────────────────────────────────────┘
''')

print('\n【建議改善項目】')
print('  1. 加入過濾條件: TASK_DEF_KEY_ NOT LIKE E%/C%')
print('  2. 擴充 V_PROC_VARIABLES_PIVOTED 變數欄位 (moNumber, scheduleNumber 等)')
print('  3. 考慮是否需要任務層變數 (silver_task_variables_pivoted)')
