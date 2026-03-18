# SPA 整合 + 通知中心设计方案

## 概述

将 Forum 模块整合到主 SPA，并新增统一的通知中心功能。

## 目标

1. 消除页面跳转时的重新加载问题
2. 统一状态管理（i18n、登录状态等）
3. 提供实时通知功能（好友请求、新消息、帖子互动等）

## 架构

```
index.html (主 SPA)
├── 顶部导航栏 [Logo] [搜索] [🔔通知] [👤用户]
├── 主内容区 (hash 路由)
│   ├── #chat    - AI 聊天
│   ├── #market  - 市场行情
│   ├── #pulse   - 市场脉动
│   ├── #forum   - 论坛 (新增)
│   ├── #friends - 好友/消息
│   ├── #safety  - 安全/举报
│   └── #settings- 设置
└── 底部导航栏 (GlobalNav)
```

## 通知类型

| 类型 | 图标 | 说明 |
|------|------|------|
| 好友请求 | 👤 | 有人想加你为好友 |
| 新消息 | 💬 | 收到新私聊消息 |
| 帖子互动 | ❤️💬 | 点赞、评论你的帖子 |
| 系统更新 | 🔄 | 有新版本可更新 |
| 系统公告 | 📢 | 维护通知、功能更新等 |

## 通知数据模型

```javascript
{
  id: "notif_abc123",
  type: "friend_request",
  title: "好友請求",
  body: "Alice 想加你為好友",
  data: { from_user_id: "user_123", from_username: "Alice" },
  is_read: false,
  created_at: "2026-02-12T10:30:00Z"
}
```

## 文件结构

### 新增文件
```
web/js/
├── components/
│   ├── NotificationBell.js    # 通知图标组件
│   ├── NotificationPanel.js   # 通知面板组件
│   └── Forum.js               # Forum 组件
└── notification-service.js    # 通知服务
```

### 修改文件
- `index.html` - 添加通知图标、Forum tab
- `js/app.js` - 添加 #forum 路由
- `js/components.js` - 添加 Forum 组件模板
- `js/nav-config.js` - 更新导航配置

## 分阶段实施

### Phase 1：SPA 整合 + 基础通知 UI
- Forum 组件化并整合到主 SPA
- 通知图标和面板 UI（先用模拟数据）

### Phase 2：后端通知 API + WebSocket
- 创建 notifications 数据表
- 新增 /api/notifications API
- 扩展 WebSocket 支持通知推送

### Phase 3：其他模块整合
- 整合 Scam-tracker
- 整合 Governance

## 技术选型

- **实时通信**：WebSocket（复用现有 MessageConnectionManager）
- **UI 位置**：顶部导航栏右侧
- **状态管理**：localStorage + 内存缓存

---

设计日期：2026-02-12
