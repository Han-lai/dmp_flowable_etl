## Test 1：A 組 Pivot 壓測
```
clickhouse-benchmark --host=127.0.0.1 --port=9000 --user=default --password=default --concurrency=10 --iterations=100 --randomize < /tmp/benchmark/queries_dg3_pivot.sql 2>&1 | tee /tmp/benchmark/benchmark_dg3_pivot.txt
Loaded 7 queries.

Queries executed: 10 (142.857%).

127.0.0.1:9000, queries: 10, QPS: 9.352, RPS: 5405371.709, MiB/s: 346.558, result RPS: 617.205, result MiB/s: 0.082.

0.000%          0.487 sec.
10.000%         0.544 sec.
20.000%         0.619 sec.
30.000%         0.665 sec.
40.000%         0.683 sec.
50.000%         0.692 sec.
60.000%         0.692 sec.
70.000%         0.730 sec.
80.000%         0.730 sec.
90.000%         0.730 sec.
95.000%         0.754 sec.
99.000%         0.754 sec.
99.900%         0.754 sec.
99.990%         0.754 sec.



Queries executed: 22 (314.286%).

127.0.0.1:9000, queries: 12, QPS: 11.274, RPS: 6516292.076, MiB/s: 417.783, result RPS: 744.054, result MiB/s: 0.099.

0.000%          0.541 sec.
10.000%         0.580 sec.
20.000%         0.656 sec.
30.000%         0.662 sec.
40.000%         0.732 sec.
50.000%         0.773 sec.
60.000%         0.795 sec.
70.000%         0.804 sec.
80.000%         0.871 sec.
90.000%         0.913 sec.
95.000%         0.913 sec.
99.000%         0.914 sec.
99.900%         0.914 sec.
99.990%         0.914 sec.



Queries executed: 35 (500.000%).

127.0.0.1:9000, queries: 13, QPS: 11.773, RPS: 6805064.819, MiB/s: 436.298, result RPS: 777.027, result MiB/s: 0.103.

0.000%          0.754 sec.
10.000%         0.765 sec.
20.000%         0.772 sec.
30.000%         0.796 sec.
40.000%         0.825 sec.
50.000%         0.847 sec.
60.000%         0.852 sec.
70.000%         0.858 sec.
80.000%         0.903 sec.
90.000%         0.965 sec.
95.000%         0.965 sec.
99.000%         1.009 sec.
99.900%         1.009 sec.
99.990%         1.009 sec.



Queries executed: 44 (628.571%).

127.0.0.1:9000, queries: 9, QPS: 8.761, RPS: 5064190.148, MiB/s: 324.684, result RPS: 578.248, result MiB/s: 0.077.

0.000%          0.843 sec.
10.000%         0.949 sec.
20.000%         0.958 sec.
30.000%         0.958 sec.
40.000%         1.004 sec.
50.000%         1.011 sec.
60.000%         1.042 sec.
70.000%         1.113 sec.
80.000%         1.113 sec.
90.000%         1.117 sec.
95.000%         1.332 sec.
99.000%         1.332 sec.
99.900%         1.332 sec.
99.990%         1.332 sec.



Queries executed: 55 (785.714%).

127.0.0.1:9000, queries: 11, QPS: 10.092, RPS: 5833055.510, MiB/s: 373.979, result RPS: 666.040, result MiB/s: 0.088.

0.000%          0.654 sec.
10.000%         0.670 sec.
20.000%         0.675 sec.
30.000%         0.796 sec.
40.000%         0.827 sec.
50.000%         0.854 sec.
60.000%         0.878 sec.
70.000%         0.994 sec.
80.000%         1.181 sec.
90.000%         1.203 sec.
95.000%         1.322 sec.
99.000%         1.322 sec.
99.900%         1.322 sec.
99.990%         1.322 sec.



Queries executed: 67 (957.143%).

127.0.0.1:9000, queries: 12, QPS: 11.623, RPS: 6718034.088, MiB/s: 430.718, result RPS: 767.090, result MiB/s: 0.102.

0.000%          0.690 sec.
10.000%         0.698 sec.
20.000%         0.895 sec.
30.000%         0.916 sec.
40.000%         0.952 sec.
50.000%         1.035 sec.
60.000%         1.049 sec.
70.000%         1.059 sec.
80.000%         1.128 sec.
90.000%         1.190 sec.
95.000%         1.190 sec.
99.000%         1.349 sec.
99.900%         1.349 sec.
99.990%         1.349 sec.



Queries executed: 78 (1114.286%).

127.0.0.1:9000, queries: 11, QPS: 10.270, RPS: 5935976.352, MiB/s: 380.577, result RPS: 677.792, result MiB/s: 0.090.

0.000%          0.631 sec.
10.000%         0.734 sec.
20.000%         0.758 sec.
30.000%         0.801 sec.
40.000%         0.823 sec.
50.000%         0.875 sec.
60.000%         0.885 sec.
70.000%         0.933 sec.
80.000%         0.948 sec.
90.000%         1.146 sec.
95.000%         1.239 sec.
99.000%         1.239 sec.
99.900%         1.239 sec.
99.990%         1.239 sec.



Queries executed: 100 (1428.571%).

127.0.0.1:9000, queries: 100, QPS: 10.537, RPS: 6090515.987, MiB/s: 390.485, result RPS: 695.438, result MiB/s: 0.092.

0.000%          0.487 sec.
10.000%         0.662 sec.
20.000%         0.730 sec.
30.000%         0.782 sec.
40.000%         0.827 sec.
50.000%         0.878 sec.
60.000%         0.929 sec.
70.000%         0.977 sec.
80.000%         1.050 sec.
90.000%         1.146 sec.
95.000%         1.208 sec.
99.000%         1.332 sec.
99.900%         1.349 sec.
99.990%         1.349 sec.
```



## Test 2：A 組 Standard 壓測

```
clickhouse-benchmark --host=127.0.0.1 --port=9000 --user=default --password=default --concurrency=10 --iterations=100 --randomize < /tmp/benchmark/queries_dg3_standard.sql 2>&1 | tee /tmp/benchmark/benchmark_dg3_standard.txt
Loaded 7 queries.

Queries executed: 64 (914.286%).

127.0.0.1:9000, queries: 64, QPS: 63.665, RPS: 6133197.438, MiB/s: 440.014, result RPS: 700.311, result MiB/s: 0.105.

0.000%          0.073 sec.
10.000%         0.091 sec.
20.000%         0.100 sec.
30.000%         0.112 sec.
40.000%         0.123 sec.
50.000%         0.141 sec.
60.000%         0.151 sec.
70.000%         0.161 sec.
80.000%         0.169 sec.
90.000%         0.181 sec.
95.000%         0.188 sec.
99.000%         0.216 sec.
99.900%         0.228 sec.
99.990%         0.228 sec.



Queries executed: 100 (1428.571%).

127.0.0.1:9000, queries: 100, QPS: 62.166, RPS: 5988826.895, MiB/s: 429.657, result RPS: 683.826, result MiB/s: 0.102.

0.000%          0.073 sec.
10.000%         0.093 sec.
20.000%         0.106 sec.
30.000%         0.112 sec.
40.000%         0.124 sec.
50.000%         0.139 sec.
60.000%         0.144 sec.
70.000%         0.160 sec.
80.000%         0.169 sec.
90.000%         0.184 sec.
95.000%         0.196 sec.
99.000%         0.239 sec.
99.900%         0.264 sec.
99.990%         0.264 sec.


```



## Test 3：B 組 Pivot 壓測

```
clickhouse-benchmark --host=127.0.0.1 --port=9000 --user=default --password=default --concurrency=10 --iterations=100 --randomize < /tmp/benchmark/queries_wj2_pivot.sql 2>&1 | tee /tmp/benchmark/benchmark_wj2_pivot.txt
Loaded 7 queries.

Queries executed: 10 (142.857%).

127.0.0.1:9000, queries: 10, QPS: 9.816, RPS: 5673989.695, MiB/s: 363.780, result RPS: 647.877, result MiB/s: 0.085.

0.000%          0.499 sec.
10.000%         0.625 sec.
20.000%         0.678 sec.
30.000%         0.709 sec.
40.000%         0.715 sec.
50.000%         0.727 sec.
60.000%         0.727 sec.
70.000%         0.731 sec.
80.000%         0.732 sec.
90.000%         0.773 sec.
95.000%         0.795 sec.
99.000%         0.795 sec.
99.900%         0.795 sec.
99.990%         0.795 sec.



Queries executed: 22 (314.286%).

127.0.0.1:9000, queries: 12, QPS: 10.940, RPS: 6323470.297, MiB/s: 405.421, result RPS: 722.037, result MiB/s: 0.094.

0.000%          0.547 sec.
10.000%         0.578 sec.
20.000%         0.674 sec.
30.000%         0.683 sec.
40.000%         0.722 sec.
50.000%         0.724 sec.
60.000%         0.725 sec.
70.000%         0.726 sec.
80.000%         0.732 sec.
90.000%         0.752 sec.
95.000%         0.752 sec.
99.000%         0.758 sec.
99.900%         0.758 sec.
99.990%         0.758 sec.



Queries executed: 40 (571.429%).

127.0.0.1:9000, queries: 18, QPS: 17.919, RPS: 10357379.202, MiB/s: 664.049, result RPS: 1182.644, result MiB/s: 0.155.

0.000%          0.574 sec.
10.000%         0.592 sec.
20.000%         0.596 sec.
30.000%         0.633 sec.
40.000%         0.656 sec.
50.000%         0.715 sec.
60.000%         0.761 sec.
70.000%         0.844 sec.
80.000%         0.861 sec.
90.000%         0.863 sec.
95.000%         0.900 sec.
99.000%         0.973 sec.
99.900%         0.973 sec.
99.990%         0.973 sec.



Queries executed: 51 (728.571%).

127.0.0.1:9000, queries: 11, QPS: 10.491, RPS: 6063844.310, MiB/s: 388.775, result RPS: 692.392, result MiB/s: 0.090.

0.000%          0.603 sec.
10.000%         0.615 sec.
20.000%         0.718 sec.
30.000%         0.727 sec.
40.000%         0.745 sec.
50.000%         0.751 sec.
60.000%         0.769 sec.
70.000%         0.796 sec.
80.000%         0.838 sec.
90.000%         0.885 sec.
95.000%         0.923 sec.
99.000%         0.923 sec.
99.900%         0.923 sec.
99.990%         0.923 sec.



Queries executed: 62 (885.714%).

127.0.0.1:9000, queries: 11, QPS: 10.939, RPS: 6322655.769, MiB/s: 405.369, result RPS: 721.944, result MiB/s: 0.094.

0.000%          0.620 sec.
10.000%         0.628 sec.
20.000%         0.677 sec.
30.000%         0.741 sec.
40.000%         0.750 sec.
50.000%         0.862 sec.
60.000%         0.868 sec.
70.000%         0.883 sec.
80.000%         0.957 sec.
90.000%         1.067 sec.
95.000%         1.089 sec.
99.000%         1.089 sec.
99.900%         1.089 sec.
99.990%         1.089 sec.



Queries executed: 75 (1071.429%).

127.0.0.1:9000, queries: 13, QPS: 12.410, RPS: 7173042.292, MiB/s: 459.890, result RPS: 819.044, result MiB/s: 0.107.

0.000%          0.557 sec.
10.000%         0.634 sec.
20.000%         0.672 sec.
30.000%         0.688 sec.
40.000%         0.688 sec.
50.000%         0.757 sec.
60.000%         0.772 sec.
70.000%         0.776 sec.
80.000%         0.824 sec.
90.000%         0.836 sec.
95.000%         0.836 sec.
99.000%         1.019 sec.
99.900%         1.019 sec.
99.990%         1.019 sec.



Queries executed: 100 (1428.571%).

127.0.0.1:9000, queries: 100, QPS: 12.382, RPS: 7156749.622, MiB/s: 458.845, result RPS: 817.184, result MiB/s: 0.107.

0.000%          0.499 sec.
10.000%         0.592 sec.
20.000%         0.634 sec.
30.000%         0.688 sec.
40.000%         0.723 sec.
50.000%         0.739 sec.
60.000%         0.769 sec.
70.000%         0.804 sec.
80.000%         0.861 sec.
90.000%         0.900 sec.
95.000%         1.000 sec.
99.000%         1.067 sec.
99.900%         1.089 sec.
99.990%         1.089 sec.
```



## Test 4：B 組 Standard 壓測

```
 clickhouse-benchmark --host=127.0.0.1 --port=9000 --user=default --password=default --concurrency=10 --iterations=100 --randomize < /tmp/benchmark/queries_wj2_standard.sql 2>&1 | tee /tmp/benchmark/benchmark_wj2_standard.txt
Loaded 7 queries.

Queries executed: 50 (714.286%).

127.0.0.1:9000, queries: 50, QPS: 48.257, RPS: 4648859.212, MiB/s: 333.523, result RPS: 530.824, result MiB/s: 0.078.

0.000%          0.080 sec.
10.000%         0.109 sec.
20.000%         0.139 sec.
30.000%         0.150 sec.
40.000%         0.163 sec.
50.000%         0.181 sec.
60.000%         0.187 sec.
70.000%         0.202 sec.
80.000%         0.216 sec.
90.000%         0.254 sec.
95.000%         0.288 sec.
99.000%         0.300 sec.
99.900%         0.300 sec.
99.990%         0.300 sec.



Queries executed: 100 (1428.571%).

127.0.0.1:9000, queries: 100, QPS: 51.418, RPS: 4953388.244, MiB/s: 355.371, result RPS: 565.596, result MiB/s: 0.084.

0.000%          0.080 sec.
10.000%         0.112 sec.
20.000%         0.127 sec.
30.000%         0.142 sec.
40.000%         0.152 sec.
50.000%         0.169 sec.
60.000%         0.183 sec.
70.000%         0.189 sec.
80.000%         0.202 sec.
90.000%         0.225 sec.
95.000%         0.258 sec.
99.000%         0.295 sec.
99.900%         0.300 sec.
99.990%         0.300 sec.
```





## Test 5：A 組資料正確性（V3/DG3/SMT/ST02 @ 12月整月）

直接 GROUP BY：

   ┌─total─┬─todo─┬─doing─┬─done─┐
1. │  5611 │ 1288 │  1220 │ 3103 │
   └───────┴──────┴───────┴──────┘

   Pivot SQL CTE Month：

   ┌─total─┬─todo─┬─doing─┬─done─┐
1. │  5611 │ 1288 │  1220 │ 3103 │
   └───────┴──────┴───────┴──────┘

逐日明細（12/25～12/31）：

  ┌─snapshot_date─┬─total_task─┬─todo_count─┬─doing_count─┬─done_count─┬─acc_todo_doing─┐
1. │    2025-12-25 │        306 │         66 │          36 │        204 │            154 │
2. │    2025-12-26 │        178 │         19 │          66 │         93 │            171 │
3. │    2025-12-27 │        291 │         22 │          29 │        240 │             97 │
4. │    2025-12-28 │         12 │          1 │           1 │         10 │             91 │
5. │    2025-12-29 │        147 │         64 │          28 │         55 │            134 │
6. │    2025-12-30 │        128 │          7 │          53 │         68 │            102 │
7. │    2025-12-31 │         49 │          3 │           8 │         38 │             69 │
   └───────────────┴────────────┴────────────┴─────────────┴────────────┴────────────────┘

   
## Test 6：B 組資料正確性（V3/WJ2/NBU/E5 @ 12月整月）
直接 GROUP BY：
   ┌─total─┬─todo─┬─doing─┬─done─┐
1. │  2808 │  308 │   235 │ 2263 │
   └───────┴──────┴───────┴──────┘


Pivot SQL CTE Month：
   ┌─total─┬─todo─┬─doing─┬─done─┐
1. │  2808 │  308 │   235 │ 2263 │
   └───────┴──────┴───────┴──────┘


   逐日明細（12/25～12/31）：
   ┌─snapshot_date─┬─total_task─┬─todo_count─┬─doing_count─┬─done_count─┬─acc_todo_doing─┐
1. │    2025-12-25 │        192 │         26 │           1 │        165 │             41 │
2. │    2025-12-26 │        148 │         56 │          12 │         80 │             77 │
3. │    2025-12-27 │        110 │         14 │           4 │         92 │             45 │
4. │    2025-12-28 │         11 │          3 │           0 │          8 │             47 │
5. │    2025-12-29 │         88 │          3 │          22 │         63 │             44 │
6. │    2025-12-30 │        264 │          8 │          60 │        196 │             96 │
7. │    2025-12-31 │        211 │          9 │           5 │        197 │             99 │
   └───────────────┴────────────┴────────────┴─────────────┴────────────┴────────────────┘


## Test 7：資料壓縮比

    ┌─database─┬─table──────────────────────────────────────────────┬─uncompressed─┬─compressed─┬─ratio─┬─────rows─┐
 1. │ bronze   │ bpm_act_hi_varinst                                 │ 4.70 GiB     │ 729.95 MiB │   6.6 │ 17345207 │
 2. │ bronze   │ bpm_act_hi_taskinst                                │ 524.16 MiB   │ 142.89 MiB │  3.67 │  1472565 │
 3. │ silver   │ .inner_id.f10d06ee-f601-4395-b73e-63d5d753fd98     │ 336.25 MiB   │ 94.76 MiB  │  3.55 │  1472565 │
 4. │ bronze   │ bpm_act_hi_procinst                                │ 216.52 MiB   │ 54.68 MiB  │  3.96 │   532554 │
 5. │ bronze   │ bpm_act_hi_identitylink                            │ 204.67 MiB   │ 20.28 MiB  │ 10.09 │  1239084 │
 6. │ bronze   │ common_flowable_task_stats                         │ 145.71 MiB   │ 26.67 MiB  │  5.46 │   389049 │
 7. │ bronze   │ common_hr_employee                                 │ 75.60 MiB    │ 19.68 MiB  │  3.84 │   127436 │
 8. │ silver   │ .inner_id.c29f8f4f-55d4-4c4f-b10e-5eddafb8ecbf     │ 38.82 MiB    │ 12.36 MiB  │  3.14 │   534853 │
 9. │ silver   │ .tmp.inner_id.c29f8f4f-55d4-4c4f-b10e-5eddafb8ecbf │ 38.82 MiB    │ 12.36 MiB  │  3.14 │   534853 │
10. │ silver   │ .inner_id.6e310672-b969-4954-b199-7595a5d15716     │ 38.82 MiB    │ 12.36 MiB  │  3.14 │   534853 │
11. │ bronze   │ common_process_role_user_mapping                   │ 4.01 MiB     │ 266.55 KiB │ 15.39 │    47472 │
12. │ gold     │ rmv_user_utilization_data                          │ 2.72 MiB     │ 78.18 KiB  │ 35.61 │    50735 │
13. │ bronze   │ common_mdm_line_desc_master                        │ 2.11 MiB     │ 363.06 KiB │  5.94 │    17331 │
14. │ gold     │ .inner_id.b29b0e6c-9e27-48e0-8c90-0c7ba7574f28     │ 1.41 MiB     │ 30.86 KiB  │ 46.88 │    25992 │
15. │ silver   │ .inner_id.d2cff398-a1fc-478d-aa34-061595c06e3e     │ 1.12 MiB     │ 169.56 KiB │  6.73 │    14969 │
16. │ gold     │ rmv_l5_task_completion_data                        │ 897.87 KiB   │ 249.25 KiB │   3.6 │    10704 │
17. │ gold     │ rmv_l5_task_completion_v2_data                     │ 897.87 KiB   │ 249.25 KiB │   3.6 │    10704 │
18. │ gold     │ .inner_id.f73f3110-0a95-4099-8e72-c82dbdc1e1b8     │ 738.22 KiB   │ 204.41 KiB │  3.61 │     8588 │
19. │ gold     │ .inner_id.f732cfcd-0a2d-46a6-9425-e6ed4cc98958     │ 738.22 KiB   │ 204.41 KiB │  3.61 │     8588 │
20. │ bronze   │ common_emp_node_role_mapping                       │ 129.82 KiB   │ 21.00 KiB  │  6.18 │     3828 │
21. │ bronze   │ bpm_act_re_procdef                                 │ 112.97 KiB   │ 12.50 KiB  │  9.04 │      450 │
22. │ bronze   │ sync_batch_control                                 │ 95.20 KiB    │ 25.93 KiB  │  3.67 │      645 │
23. │ bronze   │ common_mdm_prod_area_master                        │ 86.24 KiB    │ 31.50 KiB  │  2.74 │      866 │
24. │ bronze   │ common_emp_org_info_mapping                        │ 56.68 KiB    │ 17.80 KiB  │  3.19 │     1576 │
25. │ bronze   │ common_emp_user_group_mapping                      │ 53.48 KiB    │ 18.33 KiB  │  2.92 │     1636 │
26. │ bronze   │ common_dmp_function_config                         │ 44.56 KiB    │ 3.16 KiB   │ 14.11 │      232 │
27. │ bronze   │ common_mdm_mfg_plant_master                        │ 17.96 KiB    │ 7.40 KiB   │  2.43 │      374 │
28. │ bronze   │ common_mdm_factory_area_master                     │ 8.56 KiB     │ 3.78 KiB   │  2.26 │      102 │
29. │ bronze   │ common_dmp_function_client_mapping                 │ 7.24 KiB     │ 1.13 KiB   │  6.44 │       57 │
30. │ bronze   │ sync_table_status                                  │ 491.00 B     │ 915.00 B   │  0.54 │        4 │
31. │ bronze   │ common_mdm_mfg_site_master                         │ 443.00 B     │ 464.00 B   │  0.95 │       10 │
32. │ bronze   │ common_user_group                                  │ 406.00 B     │ 417.00 B   │  0.97 │        9 │
33. │ bronze   │ _sync_watermark                                    │ 326.00 B     │ 317.00 B   │  1.03 │        6 │
    └──────────┴────────────────────────────────────────────────────┴──────────────┴────────────┴───────┴──────────┘

## Test 8：Per-Query CPU / Memory（全部壓測完成後執行）

   ┌─queries─┬─avg_ms─┬─max_ms─┬─avg_mem────┬─max_mem────┬─avg_cpu_ms─┬─max_cpu_ms─┐
1. │     786 │  488.3 │   2080 │ 240.71 MiB │ 404.10 MiB │      257.9 │      793.4 │
   └─────────┴────────┴────────┴────────────┴────────────┴────────────┴────────────┘