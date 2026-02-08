---
name: Platform Auth Token Pattern
description: Frontend authentication token retrieval patterns and common mistakes
---

# Platform Auth Token Pattern - Frontend Authentication

This skill documents how to correctly retrieve authentication tokens in the frontend JavaScript code for PI CryptoMind.

## The Problem

**Incorrect patterns** that have caused bugs:

```javascript
// ❌ WRONG: This key doesn't exist
const token = localStorage.getItem('access_token');

// ❌ WRONG: May be null if not initialized
const token = AuthManager.currentUser.accessToken;
```

## The Correct Pattern

### Primary Source: `AuthManager.currentUser`

```javascript
// ✅ CORRECT: In-memory auth manager
if (AuthManager.currentUser && AuthManager.currentUser.accessToken) {
    const token = AuthManager.currentUser.accessToken;
    // Use token...
}
```

### Fallback: `localStorage`

```javascript
// ✅ CORRECT: Fallback to localStorage
const token = localStorage.getItem('auth_token');  // Note: 'auth_token' not 'access_token'
```

### Best Practice: Helper Function

```javascript
function _getToken() {
    // Primary: In-memory auth manager
    if (AuthManager.currentUser && AuthManager.currentUser.accessToken) {
        return AuthManager.currentUser.accessToken;
    }
    
    // Fallback: localStorage
    const stored = localStorage.getItem('auth_token');
    if (stored) {
        return stored;
    }
    
    return null;
}

// Usage
const token = _getToken();
if (!token) {
    console.error('No authentication token available');
    return;
}
```

## Authentication Flow

### 1. Pi SDK Authentication

```javascript
async function handlePiLogin() {
    try {
        const scopes = ['username', 'payments', 'wallet_address'];
        const auth = await window.Pi.authenticate(scopes, onIncompletePaymentFound);
        
        // Send to backend for verification
        const response = await fetch('/api/auth/verify-pi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ access_token: auth.accessToken })
        });
        
        const data = await response.json();
        
        // Store in AuthManager (in-memory)
        AuthManager.currentUser = {
            username: auth.user.username,
            uid: auth.user.uid,
            accessToken: auth.accessToken,  // ← Stored here
            walletAddress: data.wallet_address,
            isPremium: data.is_premium
        };
        
        // Also persist to localStorage for page reloads
        localStorage.setItem('auth_token', auth.accessToken);
        
        return true;
    } catch (error) {
        console.error('Pi authentication failed:', error);
        return false;
    }
}
```

## Common Mistakes & Fixes

### Mistake #1: Wrong localStorage Key

```javascript
// ❌ WRONG
const token = localStorage.getItem('access_token');  // Key doesn't exist

// ✅ CORRECT
const token = localStorage.getItem('auth_token');
```

**Root cause**: The key is `'auth_token'`, not `'access_token'`

### Mistake #2: Not Checking AuthManager First

```javascript
// ❌ WRONG: AuthManager might have latest token
const token = localStorage.getItem('auth_token');

// ✅ CORRECT: Check in-memory first
const token = AuthManager.currentUser?.accessToken || localStorage.getItem('auth_token');
```

**Why**: `AuthManager` is the source of truth after login. localStorage is just persistence.

## Version History

- v1.0: Initial documentation (2026-02-08)
