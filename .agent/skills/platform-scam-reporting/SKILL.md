---
name: Platform Scam Reporting & Governance System
description: Complete scam reporting system including report submission, evidence tracking, community voting consensus, and automated penalty governance.
---

# Platform Scam Reporting & Governance System Skill

## Overview

The Scam Reporting & Governance System creates a community-driven safety mechanism where users can report suspicious Pi wallets/content. PRO members act as a jury, voting on reports to reach consensus. The system automatically enforces penalties based on violation points.

**Key Files:**
- **Scam Tracker**: `core/database/scam_tracker.py` (Report/Vote/Comment Logic)
- **Governance**: `core/database/governance.py` (Consensus/Points/Penalties)
- **Frontend**: `web/scam-tracker/js/scam-tracker.js` (UI Logic)
- **API**: `api/routers/scam.py`, `api/routers/governance.py`

---

## Architecture

### System Flow

```mermaid
graph TD
    A[User Submits Report] --> B{Verify Daily Limit}
    B -->|Exceeded| C[Block Request]
    B -->|Allowed| D[Create Report (Pending)]
    D --> E[PRO Users Vote]
    E --> F{Check Consensus}
    F -->|Approved| G[Mark Verified + Punish]
    F -->|Rejected| H[Mark Disputed + Penalize Reporter]
    F -->|Pending| I[Wait for More Votes]
    G --> J[Add Violation Points]
    J --> K{Check Thresholds}
    K -->|Crossed| L[Auto-Suspend Account]
```

### Database Schema

#### scam_reports
```sql
- id: SERIAL PRIMARY KEY
- scam_wallet_address: VARCHAR(100)
- reporter_user_id: VARCHAR(100)
- scam_type: VARCHAR(50)      -- 'payment', 'fake_site', 'impersonation', etc.
- description: TEXT
- evidence_urls: JSONB        -- List of image URLs
- status: VARCHAR(20)         -- 'pending', 'verified', 'disputed'
- vote_count_approve: INTEGER
- vote_count_reject: INTEGER
- created_at: TIMESTAMP
```

#### scam_report_votes
```sql
- report_id: INTEGER REFERENCES scam_reports
- user_id: VARCHAR(100)       -- Voter ID (PRO only)
- vote_type: VARCHAR(10)      -- 'approve', 'reject'
- created_at: TIMESTAMP
- PRIMARY KEY (report_id, user_id)
```

#### user_violation_points
```sql
- user_id: VARCHAR(100)
- total_points: INTEGER
- violation_history: JSONB
- current_status: VARCHAR(20) -- 'active', 'suspended', 'banned'
- suspended_until: TIMESTAMP
```

---

## Business Rules

### Reporting Limits

| User Tier | Daily Limit |
|-----------|-------------|
| **FREE** | 5 reports/day |
| **PRO** | 10 reports/day |

*Configured in `system_config` table*

### Voting Consensus

**Requirements**:
1. **Minimum Votes**: 3 votes required to trigger decision
2. **Approval Threshold**: > 70% approval to Verify
3. **Rejection Threshold**: > 30% rejection to Dispute

**Logic (`governance.py`)**:
```python
total_votes = approve + reject
if total_votes >= MIN_VOTES:
    approval_rate = approve / total_votes
    if approval_rate >= 0.70:
        return "verified"
    elif approval_rate <= 0.30:  # i.e., >70% reject
        return "disputed"
```

### Violation System

**Point Values**:
- **Minor** (Spam, Rude): 1-3 points
- **Moderate** (Harassment, Misinfo): 5-10 points
- **Severe** (Scams, Fraud): 15-20 points
- **Critical** (Illegal, Hacks): 30+ points

**Punishment Thresholds**:
| Points | Punishment |
|--------|------------|
| 5 | Warning notification |
| 10 | 3-day suspension |
| 20 | 7-day suspension |
| 30 | 30-day suspension |
| 40 | Permanent ban |

---

## API Endpoints

### Scam Tracker (`api/routers/scam.py`)

#### POST /api/scam/reports
Submit a new scam report

**Request**:
```json
{
    "scam_wallet_address": "GABC...",
    "scam_type": "payment_fraud",
    "description": "Scammed me 100 Pi...",
    "evidence_urls": ["http://...", "http://..."]
}
```

#### GET /api/scam/reports
List reports with filtering

**Params**: `status`, `scam_type`, `sort_by`, `limit`, `offset`

#### POST /api/scam/vote
Vote on a report (PRO only)

**Request**:
```json
{
    "report_id": 123,
    "vote_type": "approve"  # or 'reject'
}
```

### Governance (`api/routers/governance.py`)

#### GET /api/governance/user-points/{user_id}
Get user's violation points and status

#### GET /api/governance/my-votes
Get current user's voting history

---

## Frontend Workflows

### ScamTrackerApp (`scam-tracker.js`)

**Key Functions**:

#### submitReport(data)
1. Check daily limit
2. Upload evidence images (if any)
3. Submit via API
4. Redirect to new report detail

#### handleVote(voteType)
1. Check if user is PRO (Frontend check)
2. Submit vote via `ScamTrackerAPI.vote()`
3. Update UI to show new vote counts
4. Toggle vote support (can switch from approve to reject)

#### checkPROStatus()
Used to show/hide voting controls. Only PRO users see vote buttons.

```javascript
async checkPROStatus() {
    // Only PRO users can vote
    if (!user.is_pro) {
        hideVoteButtons();
        showUpgradePrompt();
    }
}
```

---

## Common Issues & Solutions

### Issue 1: "Vote Failed: Permission Denied"

**Cause**: Non-PRO user attempting to vote

**Solution**:
Ensure frontend hides buttons for non-PRO users, and backend strictly enforces `is_pro` check.

```python
# Backend check
membership = get_user_membership(user_id)
if not membership['is_pro']:
    raise HTTPException(403, "Only PRO members can vote")
```

### Issue 2: Report Stuck in "Pending"

**Cause**: Has votes but hasn't reached `MIN_VOTES` (3)

**Solution**:
Encourage more PRO users to vote. System automatically checks consensus after every new vote.

### Issue 3: False Positive Punishment

**Cause**: Malicious reporting or mob voting

**Solution**:
1. **Appeal System**: Users can appeal within 7 days
2. **Reverse Decision**: Admin can manually override status
3. **Malicious Reporter Penalty**: If report is "Disputed", reporter gets violation points

---

## Modification Guidelines

### ✅ Safe Modifications

1. **Add new scam type**
   - Update frontend dropdown options
   - No backend schema change needed (varchar)

2. **Adjust consensus thresholds**
   - Modify `MIN_VOTES`, `CONSENSUS_APPROVE_THRESHOLD` in `governance.py`
   - Applies to future decisions instantly

3. **Change punishment duration**
   - Modify `PUNISHMENT_THRESHOLDS` in `governance.py`

### ❌ Dangerous Modifications

1. **Removing PRO requirement for voting**
   - **Risk**: Allows Sybil attacks (creating many free accounts to manipulate votes)
   - **Rule**: Voting MUST remain PRO-only or high-reputation only

2. **Auto-banning without consensus**
   - **Risk**: Immediate abuse of reporting system
   - **Rule**: Always require consensus or admin review before bans

3. **Deleting report history**
   - **Risk**: Losing evidence of repeat offenders
   - **Rule**: Use `is_hidden` instead of DELETE

---

## Integration with Other Systems

### Forum System
- **Report Post**: Clicking "Report" on a forum post creates a Governance Report (not Scam Report)
- **Shared Points**: Violation points are global. A scam report + forum violation accumulate points together.

### PRO Membership
- **Higher Limits**: PRO users get double report limits (10/day)
- **Voting Rights**: Only PRO users can act as jurors

---

## Testing Checklist

- [ ] Can FREE users submit reports (max 5/day)?
- [ ] Can PRO users submit reports (max 10/day)?
- [ ] Are vote buttons hidden for FREE users?
- [ ] Does 3rd vote trigger consensus check?
- [ ] Does "Verified" status auto-punish the scammer?
- [ ] Does "Disputed" status auto-punish the reporter?
- [ ] Are duplicate votes prevented (one per user)?
- [ ] Can users switch votes (Approve -> Reject)?
- [ ] Is evidence URL stored correctly?

---

## Maintenance Notes

**Last Updated**: 2026-02-08

**Future Enhancements**:
- [ ] On-chain evidence verification
- [ ] Reward system for accurate voters (Reputation score)
- [ ] AI-assisted similarity detection for duplicate reports
- [ ] Integration with global blacklists
