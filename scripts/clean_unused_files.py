"""
Python 文件清理工具
扫描项目中未被引用的 Python 文件，生成删除建议
"""
import os
from pathlib import Path
from typing import Set, Dict, List
import re

# 确保不会误删的文件（关键入口文件）
PROTECTED_FILES = {
    'api_server.py',  # 主入口
    '__init__.py',  # 包初始化
    'gunicorn.conf.py',  # 配置文件
}

# 确保不会扫描的目录
IGNORE_DIRS = {
    '.venv', '__pycache__', '.git', 'node_modules', 'dist', 'build', '.gemini'
}

def find_all_python_files(project_root: Path) -> Set[Path]:
    """找到所有 Python 文件"""
    py_files = set()
    
    for py_file in project_root.rglob("*.py"):
        # 跳过忽略目录
        if any(ignored in py_file.parts for ignored in IGNORE_DIRS):
            continue
        py_files.add(py_file)
    
    return py_files

def extract_imports_from_file(file_path: Path) -> Set[str]:
    """从文件中提取所有 import 语句"""
    imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 匹配 import 语句
        patterns = [
            r'from\s+([.\w]+)\s+import',  # from x.y import z
            r'import\s+([\w.]+)',  # import x.y
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                module = match.group(1)
                imports.add(module)
        
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return imports

def module_path_to_file(module_path: str, project_root: Path) -> Path:
    """将模块路径转换为文件路径"""
    # 转换 a.b.c 为 a/b/c.py
    parts = module_path.split('.')
    file_path = project_root / '/'.join(parts)
    
    # 尝试作为文件
    if file_path.with_suffix('.py').exists():
        return file_path.with_suffix('.py')
    
    # 尝试作为包
    if (file_path / '__init__.py').exists():
        return file_path / '__init__.py'
    
    return None

def analyze_unused_files(project_root: Path) -> Dict[str, List[Path]]:
    """分析未使用的文件"""
    all_files = find_all_python_files(project_root)
    
    # 收集所有被引用的模块
    referenced_modules = set()
    
    for py_file in all_files:
        imports = extract_imports_from_file(py_file)
        referenced_modules.update(imports)
    
    print(f"📊 找到 {len(all_files)} 个 Python 文件")
    print(f"📚 发现 {len(referenced_modules)} 个不同的引用模块")
    
    # 分析每个文件
    potentially_unused = []
    protected = []
    referenced = []
    
    for py_file in all_files:
        rel_path = py_file.relative_to(project_root)
        
        # 受保护的文件
        if py_file.name in PROTECTED_FILES:
            protected.append(py_file)
            continue
        
        # 转换为模块路径
        module_parts = list(rel_path.with_suffix('').parts)
        
        # 检查是否被引用
        is_referenced = False
        
        # 检查完整路径
        full_module = '.'.join(module_parts)
        if full_module in referenced_modules:
            is_referenced = True
        
        # 检查部分路径（例如 core.tools 引用 core.tools.calculator）
        for i in range(1, len(module_parts) + 1):
            partial = '.'.join(module_parts[:i])
            if any(partial in ref for ref in referenced_modules):
                is_referenced = True
                break
        
        if is_referenced:
            referenced.append(py_file)
        else:
            potentially_unused.append(py_file)
    
    return {
        'unused': potentially_unused,
        'protected': protected,
        'referenced': referenced
    }

def main():
    project_root = Path(__file__).parent.parent
    
    print("=" * 60)
    print("Python 文件清理分析工具")
    print("=" * 60)
    print(f"项目根目录: {project_root}")
    print()
    
    result = analyze_unused_files(project_root)
    
    print("\n📋 分析结果:")
    print(f"  - 受保护文件: {len(result['protected'])}")
    print(f"  - 被引用文件: {len(result['referenced'])}")
    print(f"  - 可能未使用: {len(result['unused'])}")
    
    if result['unused']:
        print("\n⚠️  可能未使用的文件 (需人工确认):")
        print()
        
        # 按目录分组
        by_dir = {}
        for f in result['unused']:
            dir_name = f.parent.relative_to(project_root)
            if dir_name not in by_dir:
                by_dir[dir_name] = []
            by_dir[dir_name].append(f.name)
        
        for dir_path, files in sorted(by_dir.items()):
            print(f"  📁 {dir_path}/")
            for file_name in sorted(files):
                print(f"      - {file_name}")
        
        print("\n" + "=" * 60)
        print("建议:")
        print("  1. 人工确认这些文件是否真的未使用")
        print("  2. 检查是否是测试文件、工具脚本等")
        print("  3. 确认后可以删除或移动到 archive/ 目录")
        print("=" * 60)
        
        # 生成删除脚本
        delete_script = project_root / 'scripts' / 'delete_unused_files.sh'
        with open(delete_script, 'w', encoding='utf-8') as f:
            f.write("#!/bin/bash\n")
            f.write("# 自动生成的文件删除脚本\n")
            f.write("#警告: 运行前请仔细检查！\n\n")
            
            for file_path in result['unused']:
                rel_path = file_path.relative_to(project_root)
                f.write(f"# rm \"{rel_path}\"\n")
        
        print(f"\n✅ 删除脚本已生成: {delete_script}")
        print("   (所有命令已注释，需要手动取消注释)")
    
    else:
        print("\n✅ 没有发现明显未使用的文件！")

if __name__ == "__main__":
    main()
