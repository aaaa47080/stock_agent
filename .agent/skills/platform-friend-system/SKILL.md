---
name: Platform Friend & Messaging System
description: Friends management, real-time messaging, WebSocket integration, and privacy controls.
---

# Platform Friend & Messaging System Skill

## Overview

This system handles user-to-user social interactions, including friend management (add/accept/block) and real-time private messaging (DM) via WebSockets. 

**⚠️ DISTINCTION:** 
- **User Messaging**: Handled by `messages.py` and `friends.py` (This Skill)
- **AI Chat**: Handled by `core/database/chat.py` (Different system for AI assistant sessions)

**Key Files:**
- **Backend API**: `api/routers/friends.py`, `api/routers/messages.py`
- **Database**: `core/database/friends.py`
- **Frontend**: `web/js/friends.js` (Friend list), `web/js/messages.js` (Messaging UI & WebSocket)

---

## Architecture

### System Flow

```mermaid
graph TD
    A[User A] -->|Send Friend Request| B(Friend Request Pending)
    B -->|User B Accepts| C(Friendship Created)
    C --> D[Messaging Enabled]
    D -->|Send DM| E[API /api/messages/send]
    E -->|Push via WebSocket| F[User B (Online)]
    E -->|Store in DB| G[(messages table)]
```

### Database Schema

#### friendships
```sql
- id: SERIAL PRIMARY KEY
- user_id1: VARCHAR(100)
- user_id2: VARCHAR(100)
- status: VARCHAR(20)         -- 'pending', 'accepted', 'blocked'
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
- action_user_id: VARCHAR(100) -- Last actor (who sent request/blocked)
-- Constraint: user_id1 < user_id2 (to prevent duplicate rows)
```

#### direct_messages
```sql
- id: SERIAL PRIMARY KEY
- conversation_id: INTEGER
- sender_id: VARCHAR(100)
- recipient_id: VARCHAR(100)
- content: TEXT
- is_read: BOOLEAN DEFAULT FALSE
- is_hidden_sender: BOOLEAN DEFAULT FALSE
- is_hidden_recipient: BOOLEAN DEFAULT FALSE
- created_at: TIMESTAMP
```

### WebSocket Architecture

**Endpoint**: `ws://{host}/ws/messages`
**Auth**: Handshake with `{action: "auth", token: "access_token"}`

**Events**:
- `new_message`: Incoming DM
- `read_receipt`: Message marked as read
- `error`: Auth failure or limits

---

## Business Rules

### Friend Logic
1. **Mutual Consent**: DM requires 'accepted' friendship status (unless PRO feature used).
2. **Blocking**: 'blocked' status prevents ALL interaction (requests, messages, profile view).
3. **Limits**: Max friend count (config: 500 for Free, 2000 for PRO).

### Messaging Rules
1. **Friend-Only**: By default, can only message friends.
2. **PRO Greetings**: PRO users can send "Greeting" (limited 1 msg) to non-friends to request connection.
3. **Privacy**: "Delete for me" (`is_hidden`) hides message from own view but keeps for other party.
4. **Limits**: Max message length 2000 chars. Rate limits apply to prevent spam.

---

## API Endpoints

### Friends (`api/routers/friends.py`)

#### POST /api/friends/request/{target_id}
Send friend request
**Note**: If target already requested you, auto-accepts math.

#### POST /api/friends/accept/{target_id}
Accept pending request

#### POST /api/friends/batch-accept
Accept multiple requests (List[str] user_ids)

#### POST /api/friends/block/{target_id}
Block user (terminates friendship if exists)

#### GET /api/friends/list
Get friends list
**Params**: `status` (accepted/pending/blocked)

### Messages (`api/routers/messages.py`)

#### GET /api/messages/conversations
Get active conversation list with search/pagination.

#### GET /api/messages/{conversation_id}
Get message history for a chat.

#### POST /api/messages/send
Send text message.
**Triggers**: WebSocket push to recipient.

#### POST /api/messages/mark-read
Mark conversation as read.

#### POST /api/messages/greeting (PRO ONLY)
Send 1-time greeting to non-friend.

---

## Frontend Workflows

### FriendsUI (`friends.js`)
- **Friend List**: Loads accepted friends.
- **Pending Requests**: Shows incoming requests with Accept/Reject buttons.
- **Search**: Find users by username/address.

### MessagesUI (`messages.js`)
- **WebSocket Connection**: Auto-connects on login. Handles reconnection.
- **Real-time updates**: Appends new messages to DOM without reload.
- **Unread Badges**: Updates global navbar badge via `updateUnreadBadge()`.

**WebSocket Client Example**:
```javascript
MessagesWebSocket.connect();
MessagesWebSocket.onMessage((msg) => {
    if (currentChatId === msg.conversation_id) {
        appendMessage(msg);
        markAsRead(msg.conversation_id);
    } else {
        incrementBadge();
    }
});
```

---

## Common Issues & Solutions

### Issue 1: "User not online" when sending DM

**Cause**: WebSocket disconnection or auth failure.

**Solution**:
The system falls back to database storage. The user will see the message when they next connect/refresh.
Check `MessageConnectionManager` logs in `messages.py`.

### Issue 2: Duplicate Friend Requests

**Cause**: Race condition or UI multiple clicks.

**Solution**:
Backend handles `INSERT ON CONFLICT DO NOTHING` or logic checks:
```python
# friends.py
if exists and status == 'pending':
    return {"error": "Request already sent"}
if exists and status == 'accepted':
    return {"error": "Already friends"}
```

### Issue 3: Messages not updating in real-time

**Cause**: Nginx/Proxy timeout or WebSocket closed.

**Solution**:
Frontend `messages.js` has auto-reconnect logic (exponential backoff).
Ensure server keeps ping/pong (heartbeat).

---

## Modification Guidelines

### ✅ Safe Modifications
1. **UI Styling**: Changing message bubbles, colors, layouts in `messages.html`/`chat.js`.
2. **Read Limit**: Adjusting pagination limit (default 50).
3. **Friend Limit**: Changing `MAX_FRIENDS` config constant.

### ❌ Dangerous Modifications
1. **Removing Auth from WebSocket**:
   - **Risk**: Anyone can spy on messages.
   - **Rule**: ALWAYS verify token on connection.
   
2. **Bypassing Friend Check**:
   - **Risk**: Spam & Harassment.
   - **Rule**: `send_message` MUST check friendship status (unless PRO greeting logic).

---

## Testing Checklist

- [ ] Friend Request: Send -> Pending -> Accept -> Connected.
- [ ] Block: Block user -> Check they cannot message -> Unblock.
- [ ] Real-time DM: Open 2 browsers. User A sends, User B sees instantly.
- [ ] Offline DM: User A sends, User B logs in later -> sees message.
- [ ] WebSocket Auth: Connection rejected without token.
- [ ] PRO Greeting: Can send to non-friend? (Only 1 message).

---

## Related Skills
- **platform-pro-membership**: PRO Greeting feature integration.
- **platform-scam-reporting**: Reporting abusive messages.

---

## Maintenance Notes

**Last Updated**: 2026-02-08

**WebSocket Debugging**:
Check browser console for `MessagesWebSocket` logs. Backend logs `api/utils/logger.py`.

**Future Enhancements**:
- [ ] Group chats
- [ ] Image/File attachments in DMs
- [ ] E2E Encryption
- [ ] Typing indicators ("User is typing...")
