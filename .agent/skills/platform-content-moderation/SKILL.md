---
name: Platform Content Moderation & Consensus
description: Decentralized content moderation system using community voting, consensus algorithms, and automated penalties.
---

# Platform Content Moderation Skill

## Overview

The Platform Content Moderation system acts as a decentralized court. Instead of relying solely on centralized moderators, it empowers the **PRO Community** to police content and compliance through a voting consensus mechanism.

**Core Philosophy:**
- **Report**: Any user can report violations.
- **Vote**: Only high-reputation (PRO) users can act as jury.
- **Consensus**: Actions differ based on "Clear Consensus" vs "Controversial".
- **Penalty**: Automated violation points system leads to temporary or permanent bans.

**Key Files:**
- **Core Logic**: `core/database/governance.py` (General), `core/database/scam_tracker.py` (Scam Specific)
- **Frontend**: `web/scam-tracker/js/scam-tracker.js`
- **Config**: Thresholds defined in `governance.py`.

---

## Architecture

### 1. Unified Consensus Engine
Both Scam Reporting and General Content Reporting share the same consensus logic:

| Status | Condition | Action |
|--------|-----------|--------|
| **Pending** | Votes < `MIN_VOTES_REQUIRED` (3) | Waiting for more jurors. |
| **Approved** | Approval Rate >= `CONSENSUS_APPROVE_THRESHOLD` (70%) | Content Hidden / User Punished. |
| **Rejected** | Approval Rate <= `CONSENSUS_REJECT_THRESHOLD` (30%) | Report Dismissed / Reporter Penalized (if abusive). |
| **Disputed** | 30% < Approval Rate < 70% | Requires Admin Manual Review. |

### 2. Dual Reporting Channels

#### A. Scam Tracker (Transactions)
*Focus: Fraudulent Wallet Addresses*
- **Table**: `scam_reports`, `scam_votes`
- **Evidence**: `tx_hash`, screenshots (links).
- **Outcome**: Wallet address flagged system-wide.

#### B. Content Governance (Posts/Comments)
*Focus: Toxic Behavior, Spam, NSFW*
- **Table**: `content_reports`, `content_votes`, `user_violations`
- **Evidence**: Post/Comment Content.
- **Outcome**: Content hidden, User muted.

---

## Database Schema

### governance.py Tables

#### content_reports
```sql
- id: SERIAL PRIMARY KEY
- target_id: VARCHAR(100) -- user_id of violator
- content_type: 'post' | 'comment'
- content_id: INTEGER
- reason: 'spam' | 'abuse' | 'scam' | 'nsfw'
- status: 'pending' | 'approved' | 'rejected' | 'disputed'
```

#### content_votes
```sql
- report_id: INTEGER
- voter_user_id: VARCHAR(100) -- Must be PRO
- vote: 'approve' (Guilty) | 'reject' (Innocent)
```

#### user_violations
Tracks the "Criminal Record" of a user.
```sql
- user_id: VARCHAR(100)
- points: INTEGER -- Accumulates over time
- violation_level: 'warning' | 'minor' | 'major' | 'critical'
```

---

## Workflows

### 1. Reporting Flow
1. **User** clicks "Report" on a post.
2. **System** checks `check_daily_report_limit` (Prevents spamming reports).
3. **Database** creates `content_report` with status `pending`.
4. **Notification** sent to PRO users (optional/future).

### 2. Voting Flow (Jury Duty)
1. **PRO User** views "Pending Reports" queue.
2. **PRO User** casts vote (`approve` or `reject`).
3. **System** triggers `check_report_consensus`:
   - Calculates `approve_count` / `total_votes`.
   - If threshold met -> `finalize_report`.

### 3. Penalty Automation (`finalize_report`)
If status becomes **Approved**:
1. **Hide Content**: `update_post(status='hidden')`.
2. **Assign Points**: `add_violation_points(user_id, points)`.
   - Warning: 0 pts
   - Minor: 10 pts
   - Major: 30 pts
   - Critical: 100 pts (Instant Ban)
3. **Check Thresholds**:
   - If total points > 50 -> 3 Day Mute.
   - If total points > 100 -> Permanent Ban.

---

## Configuration

**Adjust these constants in `core/database/governance.py` to tune sensitivity:**

```python
MIN_VOTES_REQUIRED = 3          # Minimum votes before decision
CONSENSUS_APPROVE_THRESHOLD = 0.70  # 70% guilty votes needed to ban
CONSENSUS_REJECT_THRESHOLD = 0.30   # <30% guilty votes -> Innocent
DEFAULT_DAILY_REPORT_LIMIT = 5
PRO_DAILY_REPORT_LIMIT = 10
```

---

## Common Issues

### Issue 1: "Mob Rule" / Brigading
**Risk**: Users ganging up to ban someone.
**Mitigation**:
1. Only **PRO** members can vote (Paywall filter).
2. Report limits prevent mass-reporting.
3. `Disputed` status (30-70% split) forces manual admin review.

### Issue 2: Low Participation
**Risk**: Reports stay pending forever.
**Solution**: Implement "Jury Rewards" (Future) - Pay PRO users small Pi tip for correct voting consensus.

---

## Related Skills
- **platform-scam-reporting**: Specific details on the Scam Tracker UI.
- **platform-pro-membership**: Defines who counts as a "PRO" juror.
