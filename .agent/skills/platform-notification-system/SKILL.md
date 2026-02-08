---
name: Platform Notification System (Design Spec)
description: Design specification for a unified notification system. Currently, notifications are fragmented across Toast, Messages, and Polling.
---

# Platform Notification System Skill (Design Spec)

> ⚠️ **STATUS: PLANNED / PARTIALLY IMPLEMENTED**
> 
> This document outlines the *proposed* architecture for a unified notification system. Currently, the platform uses fragmented mechanisms (Toast, Direct WebSocket, Polling) without a centralized notification database.

## 1. Current State (As-Is)

Currently, "notifications" are handled by disparate systems:

| Type | Mechanism | Persistence | Real-time? |
|------|-----------|-------------|------------|
| **UI Updates** | `showToast()` (Frontend) | ❌ No | ✅ Yes (Immediate) |
| **Private Messages** | `MessagesWebSocket` + `direct_messages` DB | ✅ Yes | ✅ Yes (WebSocket) |
| **Friend Requests** | `get_pending_count()` (Polling) | ✅ Yes (DB) | ❌ No (Requires refresh) |
| **System Alerts** | `alert_dispatcher.py` (Telegram/Email) | ❌ No (External) | ✅ Yes |

### Limitations
- No history of "System" notifications (e.g., "You received a tip").
- No offline support for critical alerts (unless checked manually).
- No unified "Red Dot" badge for all activity (Friends + Messages + System).

---

## 2. Proposed Architecture (To-Be)

A unified system where all events flow into a central `notifications` table and are pushed via WebSocket.

### Database Schema

```sql
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,    -- Recipient
    type VARCHAR(50) NOT NULL,        -- 'friend_req', 'tip_received', 'post_mention', 'system'
    title VARCHAR(200),
    content TEXT,
    reference_id VARCHAR(100),        -- Related ID (e.g., post_id, tx_hash)
    reference_url VARCHAR(500),       -- Click action URL
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for speed
CREATE INDEX idx_notifications_user_read ON notifications(user_id, is_read);
```

### WebSocket Protocol Extension

Extend existing `ws://{host}/ws/messages` to handle general notifications:

**Server -> Client Payload:**
```json
{
    "type": "notification",
    "data": {
        "id": 123,
        "category": "tip",
        "title": "You received 10 Pi!",
        "url": "/forum/post/456",
        "timestamp": "2025-01-01T12:00:00Z"
    }
}
```

---

## 3. Implementation Plan

### Step 1: Database Migration
Create the `notifications` table using the schema above.

### Step 2: Backend API (`api/routers/notifications.py`)

```python
@router.get("/api/notifications")
def get_notifications(limit=50, offset=0):
    # Return paginated list
    pass

@router.post("/api/notifications/mark-read")
def mark_read(notification_ids: List[int]):
    # Update is_read = True
    pass
    
@router.get("/api/notifications/badge")
def get_badge_count():
    # Return count of unread notifications
    pass
```

### Step 3: Event Triggers

Modify existing logic to inject notifications:

**Friend Request (`core/database/friends.py`):**
```python
def send_friend_request(...):
    # ... existing logic ...
    create_notification(
        user_id=target_id,
        type='friend_request',
        title='New Friend Request',
        content=f'{sender_name} wants to be friends',
        reference_url='/friends'
    )
```

**Tip Received (`core/database/forum.py`):**
```python
def create_tip(...):
    # ... existing logic ...
    create_notification(
        user_id=recipient_id,
        type='tip_received',
        title='You received a tip!',
        content=f'Someone tipped you {amount} Pi',
        reference_url=f'/forum/post.html?id={post_id}'
    )
```

### Step 4: Frontend Integration

1. **Notification Center UI**: Add a "Bell" icon to the header.
2. **WebSocket Handler**: Listen for `type: "notification"` events.
3. **Toast Integration**: Show Toast ONLY when real-time notification arrives.

---

## 4. Workflows

### User Story: Receiving a Tip (Future State)

1. **User A** tips User B's post.
2. **Backend**:
   - Records tip transaction.
   - Inserts row into `notifications` table for User B.
   - Pushes WebSocket event to User B (if online).
3. **User B (Online)**:
   - Sees "Bell" icon show red dot.
   - Sees Toast: "You received 1.0 Pi!".
4. **User B (Offline)**:
   - Logs in later.
   - "Bell" icon shows red dot (fetched via API).
   - Clicks Bell -> Sees list of missed tips.

---

## 5. Maintenance Notes

**Design Owner**: [Current Developer]
**Target Phase**: Phase 2/3
**Dependencies**: Requires `platform-friend-system` and `platform-forum-system` to be stable first.
