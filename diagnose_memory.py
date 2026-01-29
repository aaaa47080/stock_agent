#!/usr/bin/env python3
"""
記憶體診斷腳本 - 分析應用的記憶體消耗
"""
import os
import sys
from collections import Counter

def scan_database_connections():
    """掃描所有使用 get_connection() 的地方"""
    print("="*60)
    print("📊 數據庫連接使用分析")
    print("="*60)
    
    connection_files = []
    connection_count = 0
   
    for root, dirs, files in os.walk("core/database"):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    count = content.count("get_connection()")
                    if count > 0:
                        connection_files.append((filepath, count))
                        connection_count += count
    
    # 也檢查 core/audit.py
    audit_path = "core/audit.py"
    if os.path.exists(audit_path):
        with open(audit_path, 'r', encoding='utf-8') as f:
            content = f.read()
            count = content.count("get_connection()")
            if count > 0:
                connection_files.append((audit_path, count))
                connection_count += count
    
    print(f"\n✅ 發現 {connection_count} 次數據庫連接調用")
    print(f"📁 分布在 {len(connection_files)} 個文件中:\n")
    
    for filepath, count in sorted(connection_files, key=lambda x: x[1], reverse=True):
        print(f"   {filepath}: {count} 次")
    
    print(f"\n⚠️  問題: 每次數據庫操作都創建新連接")
    print(f"   建議: 使用連接池（如 psycopg2.pool）")
    
    return connection_count

def analyze_audit_logging():
    """分析審計日誌實現"""
    print("\n" + "="*60)
    print("🔍 審計日誌分析")
    print("="*60)
    
    audit_file = "core/audit.py"
    if not os.path.exists(audit_file):
        print("❌ 找不到 audit.py")
        return
    
    with open(audit_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 檢查是否同步寫入
    if "conn = get_connection()" in content:
        print("\n⚠️  審計日誌使用同步數據庫寫入")
        print("   每個請求都會:")
        print("   1. 創建新的數據庫連接")
        print("   2. 同步寫入審計日誌")
        print("   3. 關閉連接")
        print("\n💡 建議:")
        print("   - 使用異步隊列（如 asyncio.Queue）")
        print("   - 批量寫入審計日誌")
        print("   - 或使用後台任務處理")

def check_middleware():
    """檢查中間件配置"""
    print("\n" + "="*60)
    print("🔧 中間件分析")
    print("="*60)
    
    middleware_dir = "api/middleware"
    if not os.path.exists(middleware_dir):
        print("❌ 找不到 middleware 目錄")
        return
    
    middleware_files = [f for f in os.listdir(middleware_dir) if f.endswith('.py') and f != '__init__.py']
    
    print(f"\n✅ 發現 {len(middleware_files)} 個中間件:")
    for mw in middleware_files:
        print(f"   - {mw}")
        
        filepath = os.path.join(middleware_dir, mw)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "get_connection()" in content:
            print(f"      ⚠️  使用數據庫連接")
        if "await" not in content and "async" in content:
            print(f"      ⚠️  可能有阻塞操作")

def analyze_global_variables():
    """分析全局變量"""
    print("\n" + "="*60)
    print("🌐 全局變量分析")
    print("="*60)
    
    globals_file = "api/globals.py"
    if os.path.exists(globals_file):
        with open(globals_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("\n✅ 全局變量文件:")
        print(f"   {globals_file}")
        
        # 查找全局變量定義
        lines = content.split('\n')
        global_vars = [line.strip() for line in lines if '=' in line and not line.strip().startswith('#')]
        
        if global_vars:
            print(f"\n   發現 {len(global_vars)} 個全局變量")

def generate_recommendations():
    """生成優化建議"""
    print("\n" + "="*60)
    print("💡 記憶體優化建議")
    print("="*60)
    
    print("""
1. **數據庫連接池** (最重要！)
   - 當前: 每次操作創建新連接
   - 建議: 使用 psycopg2.pool.SimpleConnectionPool
   - 預期效果: 減少 60-80% 記憶體消耗

2. **異步審計日誌**
   - 當前: 同步寫入數據庫
   - 建議: 使用異步隊列 + 批量寫入
   - 預期效果: 減少請求延遲和記憶體峰值

3. **審計日誌清理**
   - 定期清理舊的審計日誌（保留 30-90 天）
   - 或移至歸檔表

4. **監控工具**
   - 安裝: pip install memory-profiler
   - 使用: python -m memory_profiler api_server.py

5. **數據庫查詢優化**
   - 避免 SELECT * 
   - 使用分頁限制結果集大小
   - 添加適當的索引
    """)

if __name__ == "__main__":
    print("\n🔍 開始記憶體診斷...\n")
    
    conn_count = scan_database_connections()
    analyze_audit_logging()
    check_middleware()
    analyze_global_variables()
    generate_recommendations()
    
    print("\n" + "="*60)
    print(f"✅ 診斷完成")
    print("="*60)
    print(f"\n主要發現: {conn_count} 次數據庫連接創建")
    print("建議優先處理: 實施數據庫連接池\n")
