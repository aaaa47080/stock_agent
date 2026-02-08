---
name: pi-auth
description: Pi Network authentication flow - SDK authenticate, access token verification, security rules. Use when implementing or debugging Pi login, token verification, or user identity.
---

# Pi Authentication

Implement Pi Network authentication using the Pi SDK. Pi Apps must use Pi Authentication exclusively - no email/password or third-party auth allowed.

## When to Use This Skill

- Implementing Pi login flow
- Verifying Pioneer identity on the backend
- Debugging authentication issues
- Handling access token expiry or validation errors

## SDK Authentication (Frontend)

Initialize the SDK first:
```html
<script src="https://sdk.minepi.com/pi-sdk.js"></script>
<script>Pi.init({ version: "2.0" })</script>
```

Call authenticate:
```javascript
const Pi = window.Pi;
const scopes = ['username', 'payments'];

function onIncompletePaymentFound(payment) {
    // MUST handle incomplete payments from previous sessions
    axios.post('/api/payments/incomplete', { payment });
}

Pi.authenticate(scopes, onIncompletePaymentFound)
    .then(function(auth) {
        // auth.accessToken - dynamic string, changes periodically
        // auth.user.uid    - static, app-specific Pioneer identifier
        // auth.user.username - only returned with 'username' scope
    })
    .catch(function(error) {
        console.error(error);
    });
```

### AuthResults Object
```json
{
    "accessToken": "string (dynamic, rotates at intervals)",
    "user": {
        "uid": "string (static, app-specific identifier)",
        "username": "string (only with 'username' scope)"
    }
}
```

### Available Scopes
| Scope | Purpose | Extra Data |
|-------|---------|------------|
| `username` | Get Pioneer's username | `user.username` |
| `payments` | Enable Pi payments | None |

No specific scope is required to obtain the access token itself.

## Server-Side Verification (Backend)

Verify Pioneer identity by calling the Pi Platform API `/me` endpoint:

```javascript
// Node.js example
const headers = { authorization: "Bearer " + accessToken };
const response = await axios.get("https://api.minepi.com/v2/me", { headers });
// response.data => { uid: "string", username: "string" }
```

```python
# Python example
import requests
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get("https://api.minepi.com/v2/me", headers=headers)
# response.json() => {"uid": "...", "username": "..."}
```

Returns 401 if token is invalid or tampered.

## Auth Flow for This Project

```
Pi.authenticate() -> accessToken + uid
  -> POST /api/auth/verify (send accessToken to backend)
  -> Backend calls GET api.minepi.com/v2/me (verify token)
  -> Backend creates/updates user record using verified uid
  -> Return JWT for session management
```

## Security Rules

- **NEVER** save `accessToken` or `uid` from frontend directly to database
- **ALWAYS** verify via server-side `/me` endpoint before trusting any identity
- A malicious actor can pass forged or corrupt access tokens from the frontend
- Only the `uid` returned from the `/me` API is trustworthy for DB records
- Access tokens are short-lived and dynamic - never cache them long-term
- Do not use `localStorage` as an auth fallback - must use Pi SDK only
- Disable dev-login / test-mode endpoints in production

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| 401 from `/me` | Expired or forged token | Re-authenticate via SDK |
| `Pi is undefined` | SDK not loaded | Ensure script tag before `Pi.init()` |
| Sandbox auth fails | Dev URL not registered | Register in Developer Portal |
| Missing username | Scope not requested | Add `'username'` to scopes array |
