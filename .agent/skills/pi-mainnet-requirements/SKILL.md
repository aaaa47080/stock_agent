---
name: pi-mainnet-requirements
description: Pi Network mainnet listing requirements and compliance rules. Use when checking if the app meets Pi ecosystem standards, preparing for mainnet submission, or reviewing compliance.
---

# Pi Mainnet Listing Requirements

Ensure the app meets all Pi Browser Ecosystem listing standards. Violations of any requirement will prevent mainnet listing.

## When to Use This Skill

- Preparing the app for mainnet submission
- Reviewing compliance before deployment
- Checking if a feature violates Pi ecosystem rules
- Answering questions about what's allowed in Pi Apps

## Seven Mandatory Requirements

### 1. Fully Functional App with Professional UI
The app must be fully operational with a clean, user-friendly interface. All interactive elements must function correctly.

**Checklist:**
- [ ] No broken links or dead buttons
- [ ] All forms validate and submit correctly
- [ ] Loading states and error handling for all async operations
- [ ] Responsive design for mobile (Pi Browser is mobile-first)

### 2. Developer KYC Verified
Complete identity verification through the Pi KYC process before applying.

### 3. No Trademark Violations
Domain name must NOT start with "pi".

| Domain | Status |
|--------|--------|
| `pibananas.com` | BANNED |
| `bananas.com` | OK |
| `mypiapp.com` | OK (doesn't START with "pi") |

Do not misuse Pi branding elements (logo, name, colors in misleading ways).

### 4. Pi Authentication ONLY
Integrate Pi's Authentication SDK for all user logins. No alternatives allowed.

**Banned:**
- Email / password login
- Google, Facebook, Apple sign-in
- Phone number auth
- Any third-party auth provider
- `localStorage`-based auth fallback

**Required:**
- `Pi.authenticate()` as the sole login method
- Server-side token verification via `GET api.minepi.com/v2/me`

### 5. Pi-Only Transactions
All financial transactions must use Pi exclusively.

**Banned:**
- Fiat currency payments (USD, EUR, etc.)
- Other cryptocurrency tokens
- In-app currencies convertible to fiat
- Links to exchanges

### 6. No External Redirects
Keep users within the app and Pi Browser ecosystem.

**Banned:**
- Redirects to external websites
- Opening external browsers
- Links that leave Pi Browser

**Evaluated case-by-case:**
- Essential external resources (may be allowed with justification)

### 7. Minimal Data Collection
Collect only data essential for app functionality.

**Banned:**
- Collecting emails (unless directly necessary)
- Collecting phone numbers
- Requesting unnecessary personal information
- Tracking beyond functional requirements

## Mainnet vs Testnet

| Feature | Mainnet | Testnet |
|---------|---------|---------|
| Pi value | Real Pi | Test-Pi (no value) |
| Status | Enclosed Network (firewalled) | Open for testing |
| Resets | Never | Periodic resets possible |
| External connectivity | Blocked (no exchanges) | N/A |
| API base | api.minepi.com | Sandbox via SDK |

### Current Mainnet Restrictions (Enclosed Period)
- No connectivity between Pi and other blockchains or exchanges
- Access only through Pi Wallet and Pi Browser
- Whitelisted API calls only
- Pioneer-to-Pioneer and Pioneer-to-App transfers allowed

## Sandbox / Testnet Development

1. Register Development URL in Developer Portal (develop.pi)
2. Set `sandbox: true` in `Pi.init({ version: "2.0", sandbox: true })`
3. Authorize via "Authorize Sandbox" flow between desktop and Pi mobile app
4. Use Test-Pi for all payment testing

## Compliance Review Checklist

Before submitting to mainnet, verify:

- [ ] Pi SDK is the ONLY authentication method
- [ ] `dev-login` / `test-mode` endpoints are disabled
- [ ] No email/password forms exist anywhere in the UI
- [ ] All payments use Pi exclusively
- [ ] No external redirect links
- [ ] Domain doesn't start with "pi"
- [ ] Only essential user data is collected
- [ ] Professional, polished UI with no broken features
- [ ] Developer KYC is completed
- [ ] All async operations have proper loading/error states
