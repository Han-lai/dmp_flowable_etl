import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
q = """
SELECT 
    TEXT_, 
    count() as cnt
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ = 'plant' 
  AND PROC_INST_ID_ IN (
      SELECT PROC_INST_ID_ 
      FROM bronze.bpm_act_hi_varinst 
      WHERE NAME_ = 'lineName' AND TEXT_ = 'ST02'
  )
GROUP BY TEXT_
ORDER BY cnt DESC
"""
r = client.query(q)
print("Plant values for ST02 tasks:")
for row in r.result_rows:
    print(row)
