"""
Testnet A2U Bootstrap Script
=============================
PURPOSE: Send 0.1π to 10 unique Pi users on testnet to satisfy
         Pi Network's "App to User transactions to 10 unique wallets"
         requirement for Mainnet App Wallet application.

USAGE:
  PI_API_KEY=<testnet_api_key> PI_WALLET_SEED=<testnet_wallet_seed> python scripts/testnet_a2u_bootstrap.py

REQUIREMENTS:
  pip install pi-python

IMPORTANT:
  - This script is for TESTNET ONLY
  - Run ONCE manually, never runs automatically
  - Will NOT run if TESTNET_A2U_DONE=true in environment
  - Has NO connection to api_server.py or production logic
"""

import os
import sys
import time

# Allow importing pi_python.py from the same scripts/ directory
sys.path.insert(0, os.path.dirname(__file__))

# ============================================================
# CONFIG
# ============================================================

TESTNET_API_KEY = os.getenv("PI_API_KEY", "")          # Server API Key (Testnet)
TESTNET_WALLET_SEED = os.getenv("PI_WALLET_SEED", "")  # App Wallet Private Seed (Testnet)

# UIDs from production DB (real Pi users who logged in to the app)
TARGET_UIDS = [
    "de596108-bd78-46cc-9948-4b8353ff638c",
    "a6b83013-3a3a-4ea3-8b15-6b42e7cb081e",
    "2ed34df1-0ab4-497f-a5c1-40a88001fbc6",
    "aa97f39c-42d8-4e83-80a0-112f50175892",
    "0562c1a7-d7ec-474e-9f07-ac8086a9272b",
    "12e4b538-e6f9-4cc3-830d-76e04d18f160",
    "ea724845-a7d3-456d-8f38-ba6c79cb04e8",
    "c40ae050-25f5-4e8c-a7b7-884f5ec343ed",
    "a58dccb3-bec7-4cde-bc95-3f377893281b",
    "4100f9ae-23b6-4408-9cac-47bf50e29767",
]

AMOUNT_PER_USER = 0.1
MEMO = "PI CryptoMind testnet A2U bootstrap"

# ============================================================
# SAFETY CHECKS
# ============================================================

def check_safety():
    if os.getenv("TESTNET_A2U_DONE", "").lower() == "true":
        print("✅ TESTNET_A2U_DONE=true — already completed, skipping.")
        sys.exit(0)

    if os.getenv("ENVIRONMENT", "development").lower() in ["production", "prod"]:
        print("🚨 BLOCKED: Cannot run on production environment.")
        sys.exit(1)

    if not TESTNET_API_KEY:
        print("❌ Missing PI_API_KEY. Set it as environment variable.")
        sys.exit(1)

    if not TESTNET_WALLET_SEED:
        print("❌ Missing PI_WALLET_SEED. Get it from Pi Developer Portal → Testnet Wallet.")
        sys.exit(1)

# ============================================================
# MAIN
# ============================================================

def run():
    print("=" * 55)
    print("  PI CryptoMind — Testnet A2U Bootstrap")
    print("=" * 55)

    check_safety()

    try:
        from pi_python import PiNetwork
    except ImportError:
        print("❌ pi_python.py not found. Make sure scripts/pi_python.py exists.")
        sys.exit(1)

    pi = PiNetwork()
    pi.initialize(TESTNET_API_KEY, TESTNET_WALLET_SEED, "Pi Testnet")
    print(f"✅ Pi SDK initialized (Testnet)\n")

    results = {"success": [], "failed": []}

    for i, uid in enumerate(TARGET_UIDS, 1):
        print(f"[{i}/10] Sending {AMOUNT_PER_USER}π → {uid[:16]}...")
        try:
            payment_data = {
                "amount": AMOUNT_PER_USER,
                "memo": MEMO,
                "metadata": {"bootstrap": True, "index": i},
                "uid": uid,
            }

            payment_id = pi.create_payment(payment_data)
            print(f"       payment_id: {payment_id}")

            txid = pi.submit_payment(payment_id)
            print(f"       txid: {txid}")

            payment = pi.complete_payment(payment_id, txid)
            print(f"       ✅ Done — status: {payment.get('status', 'unknown')}")
            results["success"].append(uid)

        except Exception as e:
            print(f"       ❌ Failed: {e}")
            results["failed"].append({"uid": uid, "error": str(e)})

        if i < 10:
            time.sleep(2)

    print("\n" + "=" * 55)
    print(f"  Results: {len(results['success'])}/10 successful")
    if results["failed"]:
        print("  Failed:")
        for f in results["failed"]:
            print(f"    - {f['uid'][:16]}... : {f['error']}")

    if len(results["success"]) >= 10:
        print("\n🎉 Done! You can now apply for the Mainnet App Wallet.")
    print("=" * 55)


if __name__ == "__main__":
    run()
