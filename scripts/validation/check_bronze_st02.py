import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

PLANT = 'DG3'
FACTORY = 'SMT'
LINE = 'ST02'

print(f"Checking Bronze ACT_HI_VARINST for {LINE}...")
try:
    # 1. Simple count of TEXT_ = 'ST02'
    q1 = f"SELECT count() FROM bronze.ACT_HI_VARINST_0108 WHERE TEXT_ = '{LINE}'"
    r1 = client.query(q1)
    print(f"Bronze rows with TEXT_='{LINE}': {r1.result_rows[0][0]}")

    # 2. Count linked to Plant=DG3
    q2 = f"""
    SELECT count()
    FROM bronze.ACT_HI_VARINST_0108 v
    WHERE v.TEXT_ = '{LINE}'
      AND v.PROC_INST_ID_ IN (
          SELECT PROC_INST_ID_ 
          FROM bronze.ACT_HI_VARINST_0108 
          WHERE NAME_='plant' AND TEXT_='{PLANT}'
      )
    """
    r2 = client.query(q2)
    print(f"Bronze rows linked to {PLANT}: {r2.result_rows[0][0]}")
    
except Exception as e:
    print(f"Error: {e}")
