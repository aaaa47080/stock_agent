---
name: Platform Policies & Compliance
description: Platform compliance rules, Pi SDK requirements, and content policies that must be followed when implementing or modifying features
---

# Platform Policies & Compliance Skill

## Purpose

This skill ensures that all feature implementations and modifications comply with:
1. **Platform Terms of Service** - Usage rules and restrictions
2. **Community Guidelines** - Content moderation policies
3. **Pi Network SDK Requirements** - Official Pi compliance rules that MUST NEVER be violated
4. **Payment & Membership Rules** - PRO membership and payment handling

**CRITICAL**: When implementing ANY feature, you MUST check this skill to ensure compliance.

---

## 🚨 Pi Network SDK - ABSOLUTE REQUIREMENTS

These rules are from **Pi Network official documentation** and MUST NEVER be violated under any circumstances.

### ✅ MANDATORY Requirements

1. **Authentication Method**
   - ✅ MUST use Pi SDK for authentication (`Pi.authenticate()`)
   - ✅ MUST verify access tokens on backend before granting access
   - ❌ NEVER allow email/password login or any non-Pi authentication
   - ❌ NEVER bypass Pi authentication in production (TEST_MODE is dev-only)

2. **Payment Processing**
   - ✅ MUST use Pi Payment API (`Pi.createPayment()`)
   - ✅ MUST verify payments server-side before granting benefits
   - ✅ MUST implement three-phase flow: create → approve → complete
   - ❌ NEVER accept payments outside Pi Network
   - ❌ NEVER grant PRO benefits without verified payment

3. **User Data & Privacy**
   - ✅ Pi wallet address is the primary user identifier
   - ✅ MUST respect user privacy (don't expose wallet addresses publicly without consent)
   - ❌ NEVER store sensitive Pi SDK data (access tokens) in databases
   - ❌ NEVER share user data with third parties without explicit consent

4. **Platform Branding**
   - ✅ MUST display "Powered by Pi Network" or similar attribution
   - ✅ MUST use official Pi logos and branding guidelines
   - ❌ NEVER misrepresent the platform as official Pi product

5. **Content Policies**
   - ❌ NEVER allow scams, fraud, or illegal content
   - ❌ NEVER enable market manipulation features
   - ✅ MUST implement content moderation for user-generated content

---

## 📋 Platform Terms of Service - Key Rules

### Account & Wallet Rules

**Implementation Requirements:**
- Pi wallet binding is permanent and cannot be changed
- One wallet = One account (no multi-account features)
- Account security is user's responsibility

**Code Implications:**
```python
# ✅ CORRECT: Enforce one wallet per user
def create_account(pi_wallet_address):
    if User.exists(pi_wallet_address):
        raise AccountAlreadyExists("This wallet is already registered")
    
# ❌ WRONG: Allowing wallet changes
def change_wallet(user_id, new_wallet):  # NEVER implement this
    pass
```

### Usage Restrictions

**Prohibited Features - NEVER Implement:**
- ❌ Automated trading bots or market manipulation tools
- ❌ Data scraping or mass download features
- ❌ Features that bypass rate limits
- ❌ Anonymous posting (all posts must be tied to Pi identity)
- ❌ Fake account creation or identity spoofing

**Allowed Features:**
- ✅ Market analysis and informational content
- ✅ Social features (forum, friends, messaging)
- ✅ Content reporting and moderation tools

### PRO Membership Rules

**Payment Implementation:**
```python
# ✅ CORRECT: No refunds except system errors
def handle_refund_request(payment_id, reason):
    if reason == "duplicate_charge" or reason == "service_outage_7days":
        return process_refund(payment_id)
    else:
        return reject_refund("No refunds per Terms of Service")

# ❌ WRONG: Allowing refunds for buyer's remorse
def refund_anytime(payment_id):  # NEVER implement this
    pass
```

**PRO Benefits (must be verified):**
- Unlimited forum posts (Free users: 3/day limit)
- Advanced analysis tools access
- Moderator eligibility (requires 3-person consensus)
- Increased scam report limit (10/day vs 5/day)

---

## 🛡️ Community Guidelines - Content Moderation

### Violation Severity Levels

When implementing content moderation features, use this point system:

| Violation Level | Points | Examples |
|----------------|--------|----------|
| **MINOR** | 1-3 | Spam, off-topic posts, minor rudeness |
| **MODERATE** | 5-10 | Harassment, false information, repeated spam |
| **SEVERE** | 15-20 | Scams, fraud attempts, hate speech |
| **CRITICAL** | 30+ | Illegal content, severe fraud, coordinated attacks |

### Punishment Thresholds

```python
# ✅ CORRECT: Implement cumulative point system
PUNISHMENT_THRESHOLDS = {
    5: "warning",
    10: "3_day_suspension",
    20: "7_day_suspension",
    30: "30_day_suspension",
    40: "permanent_ban"
}

def apply_punishment(user_id, total_points):
    for threshold, action in sorted(PUNISHMENT_THRESHOLDS.items()):
        if total_points >= threshold:
            continue  # Find highest applicable
    execute_punishment(user_id, action)
```

### Report System Rules

**Rate Limits (MUST enforce):**
- Free users: 5 reports/day
- PRO users: 10 reports/day
- Malicious reporters: Account suspension

**Moderation Workflow:**
```python
# ✅ CORRECT: PRO moderators need 3-person consensus
def approve_content_removal(post_id, moderator_votes):
    if len(moderator_votes) >= 3 and all(v.is_pro_member for v in moderator_votes):
        if sum(v.vote_remove for v in moderator_votes) >= 2:
            return remove_post(post_id)
    return require_admin_review(post_id)

# ❌ WRONG: Single moderator can remove content
def remove_post_single_mod(post_id, mod_id):  # NEVER implement this
    pass
```

---

## 💳 Payment & Financial Rules

### Payment Processing

**CRITICAL: All payments MUST follow Pi Payment API**

```python
# ✅ CORRECT: Three-phase payment flow
async def purchase_pro_membership(user_id):
    # Phase 1: Create payment
    payment = await pi_sdk.create_payment({
        "amount": 10.0,
        "memo": "PRO Membership - 30 days",
        "metadata": {"user_id": user_id, "type": "membership"}
    })
    
    # Phase 2: Backend approval (verify and approve)
    await verify_payment_on_backend(payment.id)
    await pi_sdk.approve_payment(payment.id)
    
    # Phase 3: Complete and grant benefits
    await pi_sdk.complete_payment(payment.id)
    await grant_pro_membership(user_id)

# ❌ WRONG: Direct database update without Pi payment
def grant_pro_for_free(user_id):  # NEVER implement this
    db.update_user(user_id, is_pro=True)
```

### Tip/Reward System

```python
# ✅ CORRECT: Tips are irreversible
def send_tip(from_user, to_user, amount, post_id):
    if amount <= 0:
        raise ValueError("Tip amount must be positive")
    
    # Create Pi payment (irreversible)
    payment = create_pi_payment(from_user, to_user, amount)
    
    # NO REFUND function - tips are final
    log_tip_transaction(payment.id, post_id)
    notify_recipient(to_user, amount)

# ❌ WRONG: Allowing tip refunds
def refund_tip(tip_id):  # NEVER implement this
    pass
```

---

## 🔍 Disclaimer & Risk Warnings

### Investment Advice Prohibition

**CRITICAL: Platform provides information only, NOT investment advice**

```python
# ✅ CORRECT: Always include disclaimer
def display_market_analysis(symbol, data):
    disclaimer = (
        "⚠️ This analysis is for informational purposes only "
        "and does not constitute investment advice. "
        "Cryptocurrency trading carries high risk."
    )
    return render_template("analysis.html", data=data, disclaimer=disclaimer)

# ❌ WRONG: Providing recommendations without disclaimer
def show_trading_signals(symbol):  # Missing disclaimer
    return "BUY signal detected"  # NEVER do this
```

### Required Disclaimers

Add these to any financial/trading features:
1. **Not Investment Advice**: "All information is for reference only"
2. **Risk Warning**: "You may lose your entire investment"
3. **Self-Responsibility**: "Users must make their own decisions"

---

## 📊 Content Moderation Checklist

Before implementing ANY user-generated content feature:

- [ ] Is content tied to verified Pi identity?
- [ ] Are rate limits enforced (posts/day)?
- [ ] Is profanity/spam filtering active?
- [ ] Can users report content?
- [ ] Is there a moderation review system?
- [ ] Are violation points tracked?
- [ ] Are punishments automatically enforced?
- [ ] Is there an appeal process (7-day window)?
- [ ] Are malicious reporters penalized?

---

## 🚫 Prohibited Features - NEVER Implement

| Feature | Reason | Alternative |
|---------|--------|-------------|
| Automated trading bots | Market manipulation | Manual analysis tools only |
| Anonymous posting | Accountability requirement | All posts require Pi identity |
| Unlimited free posts | Spam prevention | 3 posts/day for Free users |
| Non-Pi payments | Pi SDK requirement | Use Pi Payment API only |
| Email/password login | Pi SDK requirement | Use Pi.authenticate() only |
| User wallet changes | Account integrity | One wallet per account, permanent |
| Instant PRO activation | Payment verification | 3-phase payment flow required |
| Public wallet exposure | Privacy protection | Show only hashed/truncated versions |
| Third-party data sharing | Privacy policy | Require explicit user consent |

---

## ✅ Compliance Verification Template

Use this checklist before deploying ANY feature:

```markdown
## Feature Compliance Check: [Feature Name]

### Pi SDK Compliance
- [ ] ✅ Uses Pi.authenticate() for auth? (if auth-related)
- [ ] ✅ Uses Pi Payment API for payments? (if payment-related)
- [ ] ✅ Verifies tokens/payments on backend?
- [ ] ✅ No alternative authentication methods?

### Platform Terms Compliance
- [ ] ✅ No market manipulation features?
- [ ] ✅ Rate limits enforced?
- [ ] ✅ One wallet per account rule maintained?
- [ ] ✅ Content moderation implemented?

### Privacy & Security
- [ ] ✅ No sensitive data stored in DB?
- [ ] ✅ User wallet addresses protected?
- [ ] ✅ Access tokens not logged?
- [ ] ✅ Third-party data sharing requires consent?

### Disclaimers
- [ ] ✅ Investment disclaimer added? (if financial)
- [ ] ✅ Risk warnings displayed?
- [ ] ✅ Platform attribution present?

### Content Policies
- [ ] ✅ Scam detection active?
- [ ] ✅ Report system functional?
- [ ] ✅ Violation points tracked?
- [ ] ✅ Punishments auto-enforced?

**Sign-off**: Feature is compliant and ready for deployment: YES / NO
```

---

## 🎯 Usage Examples

### Example 1: Adding a New Forum Feature

**Feature**: Allow users to create polls

**Compliance Check**:
```python
# ✅ CORRECT Implementation
class ForumPoll:
    def create(self, user_id, poll_data):
        # Check post limits
        if not user.is_pro and user.posts_today >= 3:
            raise RateLimitExceeded("Free users: 3 posts/day")
        
        # Verify Pi identity
        if not verify_pi_auth(user_id):
            raise Unauthorized("Pi authentication required")
        
        # Create poll with moderation
        poll = Poll.create(**poll_data, creator=user_id)
        enable_content_reporting(poll.id)
        
        return poll
```

### Example 2: Adding Payment Feature

**Feature**: Allow users to boost posts visibility

**Compliance Check**:
```python
# ✅ CORRECT Implementation
async def boost_post(user_id, post_id, boost_amount):
    # MUST use Pi Payment API
    payment = await Pi.create_payment({
        "amount": boost_amount,
        "memo": f"Boost post #{post_id}",
        "metadata": {"type": "post_boost", "post_id": post_id}
    })
    
    # Backend verification
    if not await verify_payment(payment.id):
        raise PaymentVerificationFailed()
    
    # Apply boost only after payment confirmed
    await apply_post_boost(post_id, boost_amount)
    
    # NO REFUNDS - per Terms of Service
    log_irreversible_payment(payment.id)
```

---

## 📚 Related Skills

- **pi-auth**: Pi Network authentication implementation
- **pi-payments**: Pi Payment API integration
- **pi-mainnet-requirements**: Pi mainnet compliance checklist
- **platform-db-pattern**: Database function conventions

---

## 🔄 Skill Maintenance

**Last Updated**: 2026-02-08

**Update Triggers**:
- Pi Network SDK updates or policy changes
- Platform Terms of Service revisions
- New compliance requirements from legal/regulatory
- Community Guidelines major revisions

**Verification**: Check Pi Developer Portal regularly for SDK updates.
