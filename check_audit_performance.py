"""
审计日志性能监控脚本（简化版）

用于检查审计日志的写入频率、数据量大小和最常记录的操作
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from core.database.connection import get_connection


def format_size(bytes_size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def check_audit_logs_performance():
    """检查审计日志性能指标"""
    try:
        conn = get_connection()
        c = conn.cursor()
    except Exception as e:
        print(f"❌ 无法连接数据库: {e}")
        print("   请确保数据库已启动且 .env 配置正确")
        return
    
    print("=" * 80)
    print("📊 审计日志性能报告")
    print("=" * 80)
    print(f"⏰ 报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 1. 总体统计
        print("📈 总体统计")
        print("-" * 80)
        c.execute("SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM audit_logs")
        result = c.fetchone()
        
        if result and result[0]:
            total_count, earliest, latest = result
            print(f"   总记录数: {total_count:,}")
            print(f"   最早记录: {earliest}")
            print(f"   最新记录: {latest}")
            
            if earliest and latest:
                duration = (latest - earliest).total_seconds() / 3600
                if duration > 0:
                    avg_per_hour = total_count / duration
                    print(f"   平均速率: {avg_per_hour:.1f} 条/小时")
        else:
            print("   ℹ️  数据库中暂无审计记录")
        print()
        
        # 2. 最近1小时统计
        print("🕐 最近1小时统计")
        print("-" * 80)
        c.execute("""
            SELECT COUNT(*) FROM audit_logs
            WHERE created_at > NOW() - INTERVAL '1 hour'
        """)
        hour_count = c.fetchone()[0] or 0
        print(f"   记录数: {hour_count:,} 条")
        
        if hour_count > 0:
            estimated_size = hour_count * 2 * 1024
            print(f"   估算写入量: {format_size(estimated_size)}")
            print(f"   估算速率: {format_size(estimated_size)}/小时")
            
            if hour_count > 100:
                print(f"   ⚠️  写入频率较高，建议检查是否有高频端点未过滤")
            else:
                print(f"   ✅ 写入频率正常")
        else:
            print(f"   ✅ 最近1小时无审计日志写入（或无活动）")
        print()
        
        # 3. 最近24小时统计
        print("📅 最近24小时统计")
        print("-" * 80)
        c.execute("""
            SELECT COUNT(*) FROM audit_logs
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        day_count = c.fetchone()[0] or 0
        print(f"   记录数: {day_count:,} 条")
        
        if day_count > 0:
            estimated_size = day_count * 2 * 1024
            print(f"   估算写入量: {format_size(estimated_size)}/天")
            print(f"   平均速率: {format_size(estimated_size / 24)}/小时")
        print()
        
        # 4. 最常记录的操作
        print("🔝 最常记录的操作 (最近24小时)")
        print("-" * 80)
        c.execute("""
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY action
            ORDER BY count DESC
            LIMIT 15
        """)
        
        rows = c.fetchall()
        if rows:
            print(f"   {'操作':<40} {'次数':>10}")
            print(f"   {'-' * 40} {'-' * 10}")
            for action, count in rows:
                print(f"   {action:<40} {count:>10,}")
        else:
            print(f"   ✅ 最近24小时无审计日志")
        print()
        
        # 5. 按端点统计
        print("🌐 最常记录的端点 (最近24小时)")
        print("-" * 80)
        c.execute("""
            SELECT endpoint, COUNT(*) as count
            FROM audit_logs
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY endpoint
            ORDER BY count DESC
            LIMIT 10
        """)
        
        rows = c.fetchall()
        if rows:
            print(f"   {'端点':<50} {'次数':>10}")
            print(f"   {'-' * 50} {'-' * 10}")
            for endpoint, count in rows:
                print(f"   {endpoint:<50} {count:>10,}")
        print()
        
        # 6. 数据完整性检查
        print("⚠️  数据完整性检查")
        print("-" * 80)
        
        # 检查是否有不应该记录的高频端点
        high_freq_patterns = [
            ('%/health%', '健康检查'),
            ('%/ready%', '就绪检查'),
            ('%/static%', '静态资源'),
            ('%/js/%', 'JS文件'),
            ('%/css/%', 'CSS文件'),
        ]
        
        all_good = True
        for pattern, name in high_freq_patterns:
            c.execute("""
                SELECT COUNT(*) FROM audit_logs
                WHERE endpoint LIKE %s AND created_at > NOW() - INTERVAL '1 hour'
            """, (pattern,))
            count = c.fetchone()[0] or 0
            
            if count > 0:
                print(f"   ⚠️  发现 {count} 条{name}记录（应该被过滤）")
                all_good = False
        
        if all_good:
            print(f"   ✅ 所有高频端点已正确过滤")
        print()
        
        # 7. 优化建议
        print("💡 优化建议")
        print("-" * 80)
        
        # 检查旧数据
        c.execute("""
            SELECT COUNT(*) FROM audit_logs
            WHERE created_at < NOW() - INTERVAL '90 days'
        """)
        old_count = c.fetchone()[0] or 0
        
        if old_count > 0:
            print(f"   📦 发现 {old_count:,} 条超过90天的记录")
            print(f"      建议执行清理: DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '90 days';")
        else:
            print(f"   ✅ 无超过90天的旧数据")
        
        # 检查总量
        c.execute("SELECT COUNT(*) FROM audit_logs")
        total = c.fetchone()[0] or 0
        
        if total > 100000:
            print(f"   📊 审计日志总量较大 ({total:,} 条)，考虑定期归档")
        
        print()
        print("=" * 80)
        print("✅ 检查完成！")
        print()
        print("💡 提示:")
        print("   - 数据库审计: 只记录敏感操作（登录、支付、发帖等）")
        print("   - 日志文件: 查看 api_server.log 了解所有API流量")
        print("   - 实时监控: tail -f api_server.log")
        print()
        
    except Exception as e:
        print(f"❌ 执行查询时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == "__main__":
    check_audit_logs_performance()
