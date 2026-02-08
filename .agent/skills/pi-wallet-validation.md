---
name: pi-wallet-validation
description: Pi Network wallet address and transaction hash format validation. Use when validating Pi/Stellar addresses, checking wallet format, or handling transaction hashes.
---

# Pi Wallet Address & Transaction Validation

Validate Pi Network wallet addresses and transaction hashes. Pi is built on the Stellar blockchain, so addresses follow Stellar's Base32 encoding format.

## When to Use This Skill

- Validating wallet address input from users
- Building forms that accept Pi wallet addresses
- Verifying transaction hash format
- Frontend or backend address validation

## Wallet Address Format

| Property | Value |
|----------|-------|
| Length | Exactly 56 characters |
| Prefix | Always starts with `G` |
| Encoding | Base32: A-Z and 2-7 only |
| Invalid chars | 0, 1, 8, 9, lowercase letters |
| Regex | `^G[A-Z234567]{55}$` |

### Valid Examples
```
GBDEVU63Y6NTHJQQZIKVTC23NWLQVP3WJ2RI2OTSJTNYOIGICST6DITI
GABC234567ABCDEFGHIJKLMNOPQRSTUVWXYZ234567ABCDEFGHIJKLMNO
```

### Invalid Examples
```
GABC1234...   (contains 1, 8, 9, 0 - not in Base32)
gabc2345...   (lowercase not allowed)
HABC2345...   (doesn't start with G)
GABC2345      (too short, must be 56 chars)
```

## JavaScript Validation

```javascript
function isValidPiAddress(address) {
    return /^G[A-Z234567]{55}$/.test(address);
}

// Usage - always uppercase first
const input = userInput.trim().toUpperCase();
if (!isValidPiAddress(input)) {
    showError('Invalid wallet address');
}
```

## Python Validation

```python
import re

def validate_pi_address(address: str) -> tuple[bool, str]:
    if not address or not isinstance(address, str):
        return False, "Address cannot be empty"
    address = address.strip().upper()
    if len(address) != 56:
        return False, f"Must be 56 chars (got {len(address)})"
    if not address.startswith('G'):
        return False, "Must start with 'G'"
    if not re.match(r'^G[A-Z234567]{55}$', address):
        return False, "Invalid characters (only A-Z and 2-7 allowed)"
    return True, ""
```

## Transaction Hash Format

| Property | Value |
|----------|-------|
| Length | Exactly 64 characters |
| Encoding | Hexadecimal (0-9, a-f) |
| Regex | `^[a-fA-F0-9]{64}$` |

### JavaScript
```javascript
function isValidTxHash(hash) {
    return /^[a-f0-9]{64}$/.test(hash.toLowerCase());
}
```

### Python
```python
def validate_tx_hash(tx_hash: str) -> tuple[bool, str]:
    if not tx_hash:
        return True, ""  # Optional field
    tx_hash = tx_hash.strip()
    if len(tx_hash) != 64:
        return False, f"Must be 64 chars (got {len(tx_hash)})"
    if not re.match(r'^[a-fA-F0-9]{64}$', tx_hash):
        return False, "Must be hexadecimal characters only"
    return True, ""
```

## Masking for Display

Mask wallet addresses to protect privacy when displaying publicly:

```python
def mask_wallet(address: str, show: int = 4) -> str:
    if len(address) <= show * 2:
        return address
    return f"{address[:show]}...{address[-show:]}"
# GBDE...DITI
```

```javascript
function maskWallet(address, show = 4) {
    if (address.length <= show * 2) return address;
    return `${address.slice(0, show)}...${address.slice(-show)}`;
}
```

## This Project's Implementation

- Backend validator: `core/validators/pi_address.py` (`validate_pi_address`, `validate_pi_tx_hash`, `mask_wallet_address`)
- Frontend validator: `web/js/safetyTab.js` (`_isValidPiAddress`, `_isValidTxHash`)
- Always `.toUpperCase()` user input before validating
- Always validate both frontend AND backend (never trust client-side only)
