---
name: Platform Payment Flows
description: Platform-specific payment business logic, including Post Fees, Tipping, and PRO Membership upgrades.
---

# Platform Payment Flows Skill

## Overview

This skill details the **business logic** for payments within the platform. While `pi-payments` covers the technical SDK integration, this skill focuses on how payments are applied to specific features: **Creating Posts**, **Tipping**, and **PRO Membership**.

**Payment Model:**
1. **Client-Side**: Initiates Pi Payment via SDK -> Gets `txid`.
2. **Server-Side**: Receives `txid` + Business Action -> Verifies -> Fulfills.

**Key Files:**
- **Frontend**: `web/js/forum.js` (Post/Tip), `web/js/premium.js` (Membership)
- **Backend**: `api/routers/forum.py` (`create_post`, `tip_post`), `api/routers/user.py` (`upgrade_to_pro`)
- **Database**: `core/database/forum.py`, `core/database/user.py`

---

## Payment Scenarios

### 1. Paid Post Creation
Users pay a small fee (e.g., 0.1 Pi) to create a post in specific boards or to bypass daily limits.

**Workflow:**
1. **Frontend**: Checks if payment is required (based on `ForumLimits`).
2. **Frontend**: Calls Pi SDK `createPayment`.
3. **Frontend**: On success, sends `createPost(data, tx_hash)` to backend.
4. **Backend**: 
   - Validates `tx_hash` format (and optionally queries blockchain).
   - Creates post with `payment_tx_hash` stored in `forum_posts`.
   - **Result**: Post is live.

### 2. Tipping
Users send direct P2P tips to content creators.

**Workflow:**
1. **Frontend**: User clicks "Tip", selects amount.
2. **Frontend**: SDK Payment to **Creator's Wallet** (Visual verification key).
3. **Frontend**: Sends `tipPost(postId, amount, tx_hash)` to backend.
4. **Backend**: 
   - Records tip in `forum_tips`.
   - Updates `tips_total` count on the post.
   - Sends notification to recipient (see `platform-notification-system`).

### 3. PRO Membership Upgrade
Users pay a monthly fee (e.g., 10 Pi) to upgrade account status.

**Workflow:**
1. **Frontend**: `PremiumManager` initiates payment to **Platform Wallet**.
2. **Frontend**: Sends `upgradeToPro(tx_hash)` to backend.
3. **Backend**:
   - Records in `membership_payments`.
   - Updates user `membership_tier` to 'PRO' and sets `membership_expires_at`.
   - **Result**: Instant access to PRO features.

---

## Database Integration

### forum_posts
Stores payment proof for the post itself.
```sql
- payment_tx_hash: VARCHAR(100) -- Proof of payment
```

### forum_tips
Records P2P transactions for history and gamification.
```sql
- from_user_id: VARCHAR(100)
- to_user_id: VARCHAR(100)
- amount: NUMERIC
- tx_hash: VARCHAR(100) -- UNIQUE constraint prevents replay
```

### membership_payments
Records revenue and subscription history.
```sql
- user_id: VARCHAR(100)
- amount: NUMERIC
- months: INTEGER
- tx_hash: VARCHAR(100) -- UNIQUE constraint
```

---

## Validation & Security

### Transaction Hash Validation
Backend uses `pi-wallet-validation` skill logic:
1. Length check (64 chars).
2. Character check (Hexadecimal).

### Replay Attack Prevention
All relevant tables (`forum_tips`, `membership_payments`) enforce `UNIQUE(tx_hash)`.
If a user tries to reuse a hash:
```python
try:
    insert_payment(tx_hash)
except IntegrityError:
    return Error("Transaction already used")
```

### On-Chain Verification (Recommended)
Currently, the system uses "Optimistic Verification" (checks hash format). 
**Future Improvement**: Backend should query Pi Blockchain API `/transactions/{tx_hash}` to verify:
1. **Sender**: Matches current user.
2. **Recipient**: Matches Platform/Creator wallet.
3. **Amount**: Matches expected cost.
4. **Memo**: Matches order ID (if used).

---

## API Endpoints

### Post & Tip (`api/routers/forum.py`)

#### POST /api/forum/posts
Payload: `{ ..., "payment_tx_hash": "..." }`

#### POST /api/forum/posts/{id}/tip
Payload: `{ "amount": 1.0, "tx_hash": "..." }`

### Membership (`api/routers/user.py`)

#### POST /api/user/upgrade
Payload: `{ "months": 1, "tx_hash": "..." }`

---

## Common Issues

### Issue 1: "Post created but payment failed"
**Cause**: User closed app after payment but before API call.
**Solution**: Frontend should cache `tx_hash` in `localStorage` and retry API call on next load.

### Issue 2: "Transaction already exists"
**Cause**: Double submission or Replay attack.
**Solution**: Show friendly error "This payment has already been processed".

### Issue 3: PRO status not updating
**Cause**: Backend error recording payment.
**Solution**: Admin tool to manual verify hash and grant PRO status.

---

## Related Skills
- **pi-payments**: SDK technical implementation.
- **platform-wallet-system**: Where history is displayed.
- **pi-wallet-validation**: Hash format rules.

---

## Maintenance Notes
**Last Updated**: 2026-02-08

**Config**:
Prices are defined in `core/config.py` or `system_config` table:
- `PRO_MONTHLY_PRICE`: 3.14 Pi
- `POST_CREATION_FEE`: 0.1 Pi
