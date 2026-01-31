# 📦 从 Neon 迁移到 Zeabur PostgreSQL

## 🔍 步骤 1: 获取完整的 Zeabur 连接信息

你已经提供了：
- ✅ 用户名: `root`
- ✅ 密码: `4fIu8g6csU3FVZDO9bWP7AM1rGvBT520`
- ✅ 数据库名: `zeabur`

还需要：
- ❓ **主机地址** (例如: `xxx.zeabur.app` 或 IP 地址)
- ❓ **端口** (通常是 `5432`)

### 在 Zeabur 控制台查找

1. 登录 https://zeabur.com
2. 进入你的 PostgreSQL 服务页面
3. 查找 "连接信息" 或 "Connection String"
4. 应该会看到类似这样的格式：

```
postgresql://root:4fIu8g6csU3FVZDO9bWP7AM1rGvBT520@<主机地址>:<端口>/zeabur?sslmode=require
```

---

## 📝 步骤 2: 更新 .env 文件

找到完整连接信息后，更新 `.env` 文件：

### 当前配置（Neon）
```env
DATABASE_URL=postgresql://neondb_owner:npg_AIDEp13oTkWb@ep-plain-credit-a11av8nt-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

### 新配置（Zeabur）- 示例
```env
# 替换为你的实际连接信息
DATABASE_URL=postgresql://root:4fIu8g6csU3FVZDO9bWP7AM1rGvBT520@<Zeabur主机地址>:5432/zeabur?sslmode=require
```

**注意**：
- 移除 `&channel_binding=require` (Zeabur 可能不需要)
- 确认是否需要 `sslmode=require`

---

## 🔄 步骤 3: 数据迁移选项

### 选项 A: 全新开始（推荐如果是测试环境）

如果 Zeabur 是全新数据库：

```powershell
# 1. 更新 .env 文件（见步骤2）

# 2. 运行数据库迁移脚本（会创建所有表）
.venv\Scripts\python.exe -c "from core.database.connection import init_db; init_db()"

# 3. 启动服务器测试
.venv\Scripts\python.exe api_server.py
```

### 选项 B: 迁移现有数据（如果需要保留数据）

```powershell
# 1. 从 Neon 导出数据
pg_dump "postgresql://neondb_owner:npg_AIDEp13oTkWb@ep-plain-credit-a11av8nt-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require" > backup.sql

# 2. 导入到 Zeabur
psql "postgresql://root:4fIu8g6csU3FVZDO9bWP7AM1rGvBT520@<Zeabur主机>:5432/zeabur" < backup.sql
```

**注意**: 如果你没安装 PostgreSQL 客户端工具，可以：
- 下载 PostgreSQL: https://www.postgresql.org/download/windows/
- 或使用 Zeabur 提供的备份功能
- 或手动重新创建数据（如果数据不重要）

---

## ✅ 步骤 4: 测试连接

更新 `.env` 后，运行测试：

```powershell
# 使用虚拟环境
.venv\Scripts\python.exe -c "from core.database.connection import get_connection; conn = get_connection(); print('✅ 数据库连接成功!'); conn.close()"
```

如果看到 "✅ 数据库连接成功!"，说明配置正确！

---

## 📊 步骤 5: 运行初始化和验证

```powershell
# 1. 初始化数据库表结构
.venv\Scripts\python.exe -c "from core.database.connection import init_db; init_db()"

# 2. 检查审计日志表是否存在
.venv\Scripts\python.exe check_audit_performance.py

# 3. 启动服务器
.venv\Scripts\python.exe api_server.py
```

---

## 🔍 常见问题

### Q: 连接失败 - "could not translate host name"
A: 检查主机地址是否正确，确认没有多余的空格或字符

### Q: 连接失败 - "password authentication failed"
A: 
- 检查密码是否正确
- 确认用户名是 `root` 而不是其他
- 密码中如果有特殊字符，可能需要 URL 编码

### Q: SSL 相关错误
A: 尝试以下几种 SSL 模式：
```env
# 方式1: 要求 SSL
DATABASE_URL=postgresql://root:xxx@host:5432/zeabur?sslmode=require

# 方式2: 偏好 SSL 但不强制
DATABASE_URL=postgresql://root:xxx@host:5432/zeabur?sslmode=prefer

# 方式3: 禁用 SSL（仅用于测试）
DATABASE_URL=postgresql://root:xxx@host:5432/zeabur?sslmode=disable
```

### Q: 需要保留 Neon 数据库吗？
A: 建议：
- 迁移成功后，保留 Neon 作为备份 7-14 天
- 确认 Zeabur 稳定后再删除 Neon
- 或保留 Neon 作为开发环境，Zeabur 作为生产环境

---

## 💡 Zeabur vs Neon 对比

### Neon 优势
- ✅ 免费额度较大
- ✅ 自动休眠（节省资源）
- ✅ 分支功能（适合开发）

### Zeabur 优势
- ✅ 与其他服务集成方便
- ✅ 部署在同一平台（延迟更低）
- ✅ 可能有更好的亚洲节点

根据你的具体需求选择！

---

## 📋 迁移检查清单

- [ ] 获取完整的 Zeabur 连接信息（主机、端口）
- [ ] 备份 Neon 数据库（如果有重要数据）
- [ ] 更新 `.env` 文件中的 `DATABASE_URL`
- [ ] 测试数据库连接
- [ ] 运行 `init_db()` 创建表结构
- [ ] 导入数据（如果需要）
- [ ] 运行 `check_audit_performance.py` 验证
- [ ] 启动服务器测试所有功能
- [ ] 监控 1-2 天确认稳定

---

## 🆘 需要帮助？

如果遇到问题，请提供：
1. 完整的错误消息
2. 你使用的 `DATABASE_URL` （密码部分可以用 *** 替换）
3. Zeabur 控制台显示的连接信息截图

我会帮你诊断！

---

> 📅 创建时间: 2026-01-30  
> 🎯 目标: 从 Neon 迁移到 Zeabur PostgreSQL  
> ⚠️  重要: 迁移前务必备份数据！
