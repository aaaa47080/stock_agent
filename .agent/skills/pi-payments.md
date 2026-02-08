---
name: pi-payments
description: Pi Network payment integration - three-phase payment flow, createPayment, server-side approve/complete, PaymentDTO. Use when implementing or debugging Pi payments.
---

# Pi Payments

Implement Pioneer-to-App payments using the Pi SDK's three-phase flow. All financial transactions in Pi Apps must use Pi exclusively - no fiat or other crypto.

## When to Use This Skill

- Implementing Pi payment flow
- Building server-side approve/complete endpoints
- Debugging payment failures or incomplete payments
- Understanding PaymentDTO structure

## Three-Phase Payment Flow

```
Phase I:   Frontend creates payment -> SDK gets paymentId -> Backend approves
Phase II:  Pioneer confirms in Pi Wallet -> Blockchain processes transaction
Phase III: SDK gets txid -> Backend completes -> Payment dialog closes
```

### Phase I - Creation & Server Approval
1. Frontend calls `Pi.createPayment(paymentData, callbacks)`
2. SDK opens Payment Flow UI (non-interactive until approved)
3. `onReadyForServerApproval(paymentId)` callback fires
4. Backend calls `POST /v2/payments/{paymentId}/approve` with Server API Key
5. Payment UI becomes interactive for Pioneer

### Phase II - Pioneer Interaction & Blockchain
1. Pioneer confirms payment in Pi Wallet
2. Pioneer signs and submits transaction to blockchain
3. Blockchain processes and returns transaction info

### Phase III - Server Completion
1. `onReadyForServerCompletion(paymentId, txid)` callback fires
2. Backend calls `POST /v2/payments/{paymentId}/complete` with `{ txid }`
3. Payment dialog closes, app becomes visible again

## Frontend Implementation

```javascript
const paymentData = {
    amount: 3.14,                    // Pi amount (number)
    memo: "Purchase item #1234",      // Shown to Pioneer (string)
    metadata: { orderId: 1234 }       // Your custom data (object)
};

const paymentCallbacks = {
    onReadyForServerApproval: function(paymentId) {
        // Send paymentId to YOUR backend
        axios.post('/api/payments/approve', { paymentId });
    },
    onReadyForServerCompletion: function(paymentId, txid) {
        // Send paymentId + txid to YOUR backend
        axios.post('/api/payments/complete', { paymentId, txid });
    },
    onCancel: function(paymentId) {
        console.log('Payment cancelled:', paymentId);
    },
    onError: function(error, payment) {
        console.error('Payment error:', error, payment);
    }
};

Pi.createPayment(paymentData, paymentCallbacks);
```

## Backend API Calls

Use the **Server API Key** (from Developer Portal) with `Authorization: Key <key>` header.

### Approve Payment
```javascript
const headers = { authorization: `Key ${SERVER_API_KEY}` };
await axios.post(
    `https://api.minepi.com/v2/payments/${paymentId}/approve`,
    null,
    { headers }
);
```

### Complete Payment
```javascript
const headers = { authorization: `Key ${SERVER_API_KEY}` };
await axios.post(
    `https://api.minepi.com/v2/payments/${paymentId}/complete`,
    { txid: transactionId },
    { headers }
);
```

### Get Payment Details
```javascript
const headers = { authorization: `Key ${SERVER_API_KEY}` };
const response = await axios.get(
    `https://api.minepi.com/v2/payments/${paymentId}`,
    { headers }
);
```

## Handling Incomplete Payments

Always handle incomplete payments from previous sessions in the authenticate callback:

```javascript
function onIncompletePaymentFound(payment) {
    // Send to backend to check status and complete or cancel
    axios.post('/api/payments/incomplete', { payment })
        .then(result => console.log('Resolved:', result))
        .catch(err => console.error('Failed to resolve:', err));
}

Pi.authenticate(scopes, onIncompletePaymentFound);
```

## PaymentDTO Structure

```json
{
    "identifier": "string (paymentId)",
    "Pioneer_uid": "string (app-specific user ID)",
    "amount": 3.14,
    "memo": "string (shown to Pioneer)",
    "metadata": { "orderId": 1234 },
    "to_address": "string (blockchain recipient wallet)",
    "created_at": "ISO 8601 timestamp",
    "status": {
        "developer_approved": true,
        "transaction_verified": true,
        "developer_completed": true,
        "canceled": false,
        "Pioneer_cancelled": false
    },
    "transaction": {
        "txid": "string (64 hex chars)",
        "verified": true,
        "_link": "string (blockchain explorer URL)"
    }
}
```

## Critical Security Rule

**Do NOT complete any payment in your app until `/complete` returns HTTP 200.** Malicious users can manipulate SDK versions to simulate payments. Only mark transactions as complete after the server-side `/complete` call succeeds.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Payment UI stays non-interactive | Backend didn't call `/approve` | Check server-side approve endpoint |
| `onReadyForServerCompletion` never fires | Pioneer didn't confirm, or blockchain delay | Wait or handle timeout |
| Incomplete payment on next auth | Previous payment wasn't completed | Implement `onIncompletePaymentFound` |
| 401 on `/approve` or `/complete` | Invalid Server API Key | Check key in Developer Portal |
