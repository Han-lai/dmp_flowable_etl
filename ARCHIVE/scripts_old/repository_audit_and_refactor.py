#!/usr/bin/env python3
"""
Repository Audit and Refactor Tool
對整個專案進行盤點並分類為：保留、封存、移除
"""

import os
import re
from pathlib import Path
from datetime import datetime

def scan_directory_structure(root_path="."):
    """掃描目錄結構"""
    structure = {}
    
    for root, dirs, files in os.walk(root_path):
        # 跳過隱藏目錄和 Python cache
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        rel_path = os.path.relpath(root, root_path)
        if rel_path == '.':
            rel_path = 'root'
        
        structure[rel_path] = {
            'dirs': dirs.copy(),
            'files': files.copy(),
            'file_count': len(files),
            'total_size': sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.exists(os.path.join(root, f)))
        }
    
    return structure

def analyze_file_references(root_path="."):
    """分析檔案引用關係"""
    references = {}
    
    # 掃描所有文字檔案尋找引用
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for file in files:
            if file.endswith(('.py', '.sql', '.js', '.md', '.yml', '.yaml', '.json', '.sh')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # 尋找檔案引用模式
                        patterns = [
                            r'from\s+([a-zA-Z_][a-zA-Z0-9_./]*)',  # Python imports
                            r'import\s+([a-zA-Z_][a-zA-Z0-9_./]*)',  # Python imports
                            r'require\([\'"]([^\'\"]+)[\'"]\)',  # JS requires
                            r'FROM\s+([a-zA-Z_][a-zA-Z0-9_.]*)',  # SQL FROM
                            r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_.]*)',  # SQL JOIN
                            r'\.([a-zA-Z_][a-zA-Z0-9_]*\.sql)',  # SQL file references
                            r'scripts/([a-zA-Z_][a-zA-Z0-9_]*\.py)',  # Script references
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, content, re.IGNORECASE)
                            for match in matches:
                                if match not in references:
                                    references[match] = []
                                references[match].append(file_path)
                
                except Exception as e:
                    continue
    
    return references

def classify_files(structure, references):
    """分類檔案"""
    classification = {
        'keep': [],      # 🟢 保留
        'archive': [],   # 🟡 封存
        'remove': []     # 🔴 移除
    }
    
    # 核心系統檔案 (必須保留)
    core_patterns = [
        r'cube/model/cubes/cube_gold_.*\.js$',  # 活躍的 Cube
        r'sql/\d+_.*\.sql$',  # 編號的 SQL 檔案
        r'sql/00_execute_all_mviews\.sql$',  # 主執行檔案
        r'docs/metric_definitions\.md$',  # 核心文件
        r'README\.md$',  # 說明文件
        r'docker/.*',  # Docker 配置
        r'cube/docker-compose\.yml$',  # Cube 配置
    ]
    
    # 測試和驗證檔案 (可封存)
    test_patterns = [
        r'scripts/.*test.*\.py$',
        r'scripts/.*verify.*\.py$',
        r'scripts/.*check.*\.py$',
        r'scripts/.*debug.*\.py$',
        r'scripts/.*diagnose.*\.py$',
        r'scripts/.*compare.*\.py$',
    ]
    
    # 臨時和重複檔案 (可移除)
    temp_patterns = [
        r'.*\.tmp$',
        r'.*\.bak$',
        r'.*~$',
        r'backup_.*\.sql$',
        r'CLAUDE\.md$',
        r'CONVERSATION_.*\.md$',
        r'MEMORY_BANK\.md$',
    ]
    
    # 停用檔案 (可封存)
    disabled_patterns = [
        r'.*\.disabled$',
    ]
    
    for path, info in structure.items():
        for file in info['files']:
            full_path = os.path.join(path, file) if path != 'root' else file
            
            # 檢查是否為核心檔案
            is_core = any(re.match(pattern, full_path) for pattern in core_patterns)
            
            # 檢查是否被引用
            is_referenced = any(full_path in refs for refs in references.values())
            
            # 檢查檔案類型
            is_test = any(re.match(pattern, full_path) for pattern in test_patterns)
            is_temp = any(re.match(pattern, full_path) for pattern in temp_patterns)
            is_disabled = any(re.match(pattern, full_path) for pattern in disabled_patterns)
            
            # 分類邏輯
            if is_core or is_referenced:
                classification['keep'].append({
                    'path': full_path,
                    'reason': 'Core system file' if is_core else 'Referenced by other files',
                    'size': info['total_size'] // len(info['files']) if info['files'] else 0
                })
            elif is_temp:
                classification['remove'].append({
                    'path': full_path,
                    'reason': 'Temporary/backup file',
                    'size': info['total_size'] // len(info['files']) if info['files'] else 0
                })
            elif is_test or is_disabled:
                classification['archive'].append({
                    'path': full_path,
                    'reason': 'Test/verification script' if is_test else 'Disabled file',
                    'size': info['total_size'] // len(info['files']) if info['files'] else 0
                })
            else:
                # 根據檔案特徵進一步判斷
                if file.endswith('.py') and 'scripts/' in full_path:
                    classification['archive'].append({
                        'path': full_path,
                        'reason': 'Utility script',
                        'size': info['total_size'] // len(info['files']) if info['files'] else 0
                    })
                elif file.endswith('.md') and any(date in file for date in ['2026', '2025']):
                    classification['archive'].append({
                        'path': full_path,
                        'reason': 'Historical documentation',
                        'size': info['total_size'] // len(info['files']) if info['files'] else 0
                    })
                else:
                    classification['keep'].append({
                        'path': full_path,
                        'reason': 'Default keep',
                        'size': info['total_size'] // len(info['files']) if info['files'] else 0
                    })
    
    return classification

def generate_refactor_plan(classification):
    """生成重構計劃"""
    plan = {
        'summary': {
            'keep_count': len(classification['keep']),
            'archive_count': len(classification['archive']),
            'remove_count': len(classification['remove']),
            'total_files': sum(len(files) for files in classification.values())
        },
        'actions': []
    }
    
    # 封存動作
    if classification['archive']:
        plan['actions'].append({
            'type': 'create_archive',
            'description': 'Create ARCHIVE directory structure',
            'commands': [
                'mkdir -p ARCHIVE/scripts',
                'mkdir -p ARCHIVE/docs',
                'mkdir -p ARCHIVE/sql',
                'mkdir -p ARCHIVE/cube'
            ]
        })
        
        for item in classification['archive']:
            if 'scripts/' in item['path']:
                target = item['path'].replace('scripts/', 'ARCHIVE/scripts/')
            elif 'docs/' in item['path']:
                target = item['path'].replace('docs/', 'ARCHIVE/docs/')
            elif 'sql/' in item['path']:
                target = item['path'].replace('sql/', 'ARCHIVE/sql/')
            elif 'cube/' in item['path']:
                target = item['path'].replace('cube/', 'ARCHIVE/cube/')
            else:
                target = f"ARCHIVE/misc/{os.path.basename(item['path'])}"
            
            plan['actions'].append({
                'type': 'move',
                'source': item['path'],
                'target': target,
                'reason': item['reason']
            })
    
    # 移除動作
    for item in classification['remove']:
        plan['actions'].append({
            'type': 'remove',
            'source': item['path'],
            'reason': item['reason']
        })
    
    return plan

def main():
    print("=== Repository Audit and Refactor ===")
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 掃描目錄結構
    print("\n1. 掃描目錄結構...")
    structure = scan_directory_structure()
    
    total_files = sum(info['file_count'] for info in structure.values())
    total_size = sum(info['total_size'] for info in structure.values())
    
    print(f"   總目錄數: {len(structure)}")
    print(f"   總檔案數: {total_files}")
    print(f"   總大小: {total_size / 1024 / 1024:.1f} MB")
    
    # 2. 分析檔案引用
    print("\n2. 分析檔案引用關係...")
    references = analyze_file_references()
    print(f"   發現 {len(references)} 個引用關係")
    
    # 3. 分類檔案
    print("\n3. 分類檔案...")
    classification = classify_files(structure, references)
    
    # 4. 生成重構計劃
    print("\n4. 生成重構計劃...")
    plan = generate_refactor_plan(classification)
    
    # 5. 輸出結果
    print("\n=== 分類結果 ===")
    
    print(f"\n🟢 保留 (Active/Useful): {plan['summary']['keep_count']} 個檔案")
    for item in sorted(classification['keep'], key=lambda x: x['path']):
        print(f"   ✅ {item['path']} - {item['reason']}")
    
    print(f"\n🟡 封存 (Archive): {plan['summary']['archive_count']} 個檔案")
    for item in sorted(classification['archive'], key=lambda x: x['path']):
        print(f"   📦 {item['path']} - {item['reason']}")
    
    print(f"\n🔴 移除 (Removable): {plan['summary']['remove_count']} 個檔案")
    for item in sorted(classification['remove'], key=lambda x: x['path']):
        print(f"   🗑️ {item['path']} - {item['reason']}")
    
    # 6. 輸出重構命令
    print(f"\n=== 重構執行計劃 ===")
    print(f"總檔案數: {plan['summary']['total_files']}")
    print(f"保留: {plan['summary']['keep_count']} | 封存: {plan['summary']['archive_count']} | 移除: {plan['summary']['remove_count']}")
    
    print(f"\n執行命令:")
    for action in plan['actions']:
        if action['type'] == 'create_archive':
            print(f"# {action['description']}")
            for cmd in action['commands']:
                print(cmd)
        elif action['type'] == 'move':
            print(f"# Move: {action['reason']}")
            print(f"mv '{action['source']}' '{action['target']}'")
        elif action['type'] == 'remove':
            print(f"# Remove: {action['reason']}")
            print(f"rm '{action['source']}'")
    
    return classification, plan

if __name__ == '__main__':
    classification, plan = main()