#!/usr/bin/env python3
"""
WJ2+NBU+E5 2025-12-30 數值驗證總結報告
"""

def main():
    print("=" * 80)
    print("WJ2+NBU+E5 2025-12-30 數值驗證總結報告")
    print("=" * 80)
    
    print("\n📊 2025-12-30 驗證結果:")
    print("┌─────────────────┬─────────┬─────────┬─────────┬─────────┬─────────┐")
    print("│ 資料來源        │ VX Type │ Total   │ Done    │ TODO    │ DOING   │")
    print("├─────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┤")
    print("│ MSSQL 原始資料  │ V3      │ 7       │ 0       │ 6       │ 1       │")
    print("│ ClickHouse Silver│ V3      │ 7       │ 0       │ 6       │ 1       │")
    print("│ ClickHouse Gold │ V3      │ 7       │ 0       │ -       │ -       │")
    print("└─────────────────┴─────────┴─────────┴─────────┴─────────┴─────────┘")
    
    print("\n📋 任務詳細分布:")
    print("┌─────────────────┬─────────────────┬─────────┬─────────┐")
    print("│ TaskDefinitionKey│ MoNumber        │ Status  │ Count   │")
    print("├─────────────────┼─────────────────┼─────────┼─────────┤")
    print("│ V3_5_1_0_1      │ 1990000003      │ TODO    │ 2       │")
    print("│ V3_5_1_0_1      │ 1990010003      │ DOING   │ 1       │")
    print("│ V3_5_1_0_1      │ 3152600035      │ TODO    │ 1       │")
    print("│ V3_5_1_0_1      │ 3152600036      │ TODO    │ 1       │")
    print("│ V3_5_1_0_1      │ 3152600037      │ TODO    │ 1       │")
    print("│ V3_5_1_0_1      │ 3152600038      │ TODO    │ 1       │")
    print("└─────────────────┴─────────────────┴─────────┴─────────┘")
    
    print("\n✅ 數據一致性驗證:")
    print("1. ✅ MSSQL vs ClickHouse Silver: 完全一致")
    print("   - 總任務數: 7 筆")
    print("   - Done 任務: 0 筆")
    print("   - TODO 任務: 6 筆")
    print("   - DOING 任務: 1 筆")
    print("   - 完成率: 0.0%")
    
    print("\n2. ✅ Silver vs Gold: 完全一致")
    print("   - VX 類型: V3 (正確)")
    print("   - 總任務數: 7 筆")
    print("   - Done 任務: 0 筆")
    print("   - 完成率: 0.0%")
    
    print("\n3. ✅ V1 歸屬邏輯修正: 成功")
    print("   - 修正前: V1 類型 (錯誤)")
    print("   - 修正後: V3 類型 (正確)")
    print("   - TaskDefinitionKey V3_5_1_0_1 正確歸類為 V3")
    
    print("\n🔍 關鍵觀察:")
    print("1. **任務類型**: 全部為 V3_5_1_0_1")
    print("2. **工單號分布**: 包含 199% 和 315% 開頭的工單")
    print("   - 1990000003 (199% 開頭)")
    print("   - 1990010003 (199% 開頭)")
    print("   - 3152600035-38 (315% 開頭)")
    print("3. **V1 歸屬邏輯**: TaskDefinitionKey 優先於工單號規則")
    print("4. **任務狀態**: 大部分為 TODO，1 筆 DOING，0 筆 DONE")
    
    print("\n🎯 修正驗證:")
    print("✅ **315% 工單號問題**: 已解決")
    print("   - 315% 工單號不再錯誤歸類為 V1")
    print("   - TaskDefinitionKey V3_5_* 正確歸類為 V3")
    
    print("✅ **199% 工單號問題**: 已解決")
    print("   - 199% 工單號不再錯誤歸類為 V1")
    print("   - TaskDefinitionKey V3_5_* 正確歸類為 V3")
    
    print("✅ **數據一致性**: 100% 通過")
    print("   - MSSQL 原始資料與 ClickHouse 完全一致")
    print("   - Silver 層與 Gold 層完全一致")
    
    print("\n" + "=" * 80)
    print("驗證結論: WJ2+NBU+E5 2025-12-30 數據完全一致，V1 歸屬邏輯修正成功")
    print("=" * 80)

if __name__ == "__main__":
    main()