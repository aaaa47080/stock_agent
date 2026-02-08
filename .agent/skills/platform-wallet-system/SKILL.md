---
name: Platform Wallet System
description: Pi Network wallet integration, user binding, and transaction history aggregation.
---

# Platform Wallet System Skill

## Overview

The Wallet System connects the platform user accounts with their Pi Network wallets. It handles wallet address binding, validation, and aggregates transaction history from various sources (tips, post fees, membership).

**⚠️ NOTE:** The platform does NOT hold user funds (custodial). It only tracks:
1. **Wallet Address**: Linked to user profile.
2. **Transaction Records**: Payments made *to* the platform or *p2p* tips tracked by the system.

**Key Files:**
- **Binding Logic**: `core/database/user.py` (`link_pi_wallet`)
- **Frontend**: `web/js/wallet.js` (Aggregates history)
- **API**: `api/routers/forum.py` (Endpoints for tips/payments)

---

## Architecture

### 1. Wallet Binding

Users must "bind" their Pi Wallet address to their account to enable:
- Receiving tips (other users need to know where to send).
- Verifying PRO membership payments.
- Building reputation (scam reports are tied to wallet address).

**Flow:**
1. User authenticates with Pi SDK (`Scopes.username`, `Scopes.payments`).
2. Frontend sends `pi_uid` and `username`.
3. Backend checks if `pi_uid` is already linked.
4. Backend stores/updates `pi_wallet_address` in `users` table.

### 2. Transaction Aggregation (Virtual Wallet)
There is **NO single transactions table**. History is aggregated on-the-fly from:

| Type | Source Table | API Endpoint |
|------|--------------|--------------|
| **Post Fees** | `forum_posts` (where payment_tx_hash is set) | `/api/forum/me/payments` |
| **Membership** | `membership_payments` | `/api/forum/me/payments` (merged) |
| **Tips Sent** | `forum_tips` (from_user_id) | `/api/forum/me/tips/sent` |
| **Tips Received** | `forum_tips` (to_user_id) | `/api/forum/me/tips/received` |

### Database Schema

#### users (Fragment)
```sql
- pi_wallet_address: VARCHAR(60) -- The bound wallet
- pi_uid: VARCHAR(100)           -- Pi Network User ID
- is_pi_verified: BOOLEAN
```

#### membership_payments
```sql
- id: SERIAL PRIMARY KEY
- user_id: VARCHAR(100)
- amount: NUMERIC
- tx_hash: VARCHAR(100)
- created_at: TIMESTAMP
- months: INTEGER
```

#### forum_tips
```sql
- id: SERIAL PRIMARY KEY
- from_user_id: VARCHAR(100)
- to_user_id: VARCHAR(100)
- post_id: INTEGER
- amount: NUMERIC
- tx_hash: VARCHAR(100)
- created_at: TIMESTAMP
```

---

## API Endpoints

### Wallet / User

#### POST /api/user/bind-wallet
Link Pi Wallet to account.
**Payload**: `{ "pi_uid": "...", "wallet_address": "..." }`

### Transaction History (`api/routers/forum.py`)

#### GET /api/forum/me/payments
Returns list of expenses (Post creation fees, PRO upgrades).

#### GET /api/forum/me/tips/sent
Returns list of tips sent to others.

#### GET /api/forum/me/tips/received
Returns list of tips received from others.

---

## Frontend Workflows

### WalletApp (`wallet.js`)

**`loadData()` logic**:
1. Parallels calls to `getMyPayments`, `getMyTipsSent`, `getMyTipsReceived`.
2. **Standardizes** data format:
   ```javascript
   {
       type: 'tip_sent' | 'tip_received' | 'post_payment' | 'membership_payment',
       amount: Number (positive for income, negative for expense),
       title: String,
       created_at: Date
   }
   ```
3. **Sorts** by `created_at` descending.
4. **Calculates** Totals (Income/Expense) for the UI.

---

## Common Issues & Solutions

### Issue 1: "Transaction missing from history"

**Cause**: API failure in one of the 3 parallel calls.
**Behavior**: Frontend might show partial data if `Promise.allSettled` is used (which it is).
**Solution**: Check browser console for specific API error. Check `tx_hash` in Pi Blockchain Explorer.

### Issue 2: Incorrect Balance / Total

**Cause**: The platform does NOT query the actual blockchain balance. It only sums up *tracked* internal actions.
**Solution**: Educate user that this is "Platform Activity History", not "Wallet Balance". For actual balance, use Pi Browser.

### Issue 3: Duplicate Transaction

**Cause**: Frontend logic or Double-click on payment.
**Solution**: Backend enforces `UNIQUE(tx_hash)` in most tables. Frontend should deduplicate by `tx_hash`.

---

## Modification Guidelines

### ✅ Safe Modifications
1. **Adding new Transaction Type**:
   - create new table (e.g. `store_purchases`)
   - add new API endpoint
   - update `wallet.js` to fetch and merge this new source.

2. **Improving Filtering**:
   - `wallet.js` `applyFilters` function can be easily extended.

### ❌ Dangerous Modifications
1. **Storing Private Keys**:
   - **CRITICAL**: NEVER store user functionality/encryption keys.
   - **Rule**: Only store PUBLIC key (`G...` address).

2. **Assuming on-chain finality**:
   - **Risk**: User claims they paid, but tx failed on chain.
   - **Rule**: Always verify `tx_hash` via Pi Backend API (server-side) before granting benefits.

---

## Future Improvements (Planned)

1. **Unified Ledger**: Create a `ledger_entries` table that mirrors all financial actions for faster querying (~10ms vs 300ms).
2. **Blockchain Sync**: Periodic background job to double-check `tx_hash` status on Pi Blockchain.

---

## Related Skills
- **pi-payments**: How the actual payment flows work.
- **platform-pro-membership**: How upgrades are processed.
