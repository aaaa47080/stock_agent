"""
Testnet A2U Bootstrap Script
=============================
PURPOSE: Send 0.1π to 10 unique Pi users on testnet to satisfy
         Pi Network's "App to User transactions to 10 unique wallets"
         requirement for Mainnet App Wallet application.

USAGE:
  python scripts/testnet_a2u_bootstrap.py

REQUIREMENTS:
  pip install pi-python

IMPORTANT:
  - This script is for TESTNET ONLY
  - Run ONCE manually, then you can leave the file or delete it
  - Will NOT run if TESTNET_A2U_DONE=true in environment
  - Has NO connection to api_server.py or production logic

BEFORE RUNNING - fill in the config below:
  1. TESTNET_API_KEY     → Pi Developer Portal → your app → Server API Key (Testnet)
  2. TESTNET_WALLET_SEED → Pi Developer Portal → your app → Testnet Wallet → Private Seed
  3. TARGET_UIDS         → 10 Pi user UIDs (ask friends to log in to testnet app once)
"""

import os
import sys
import time

# ============================================================
# CONFIG — Fill these in before running
# ============================================================

TESTNET_API_KEY = os.getenv("PI_API_KEY", "")          # Server API Key (Testnet)
TESTNET_WALLET_SEED = os.getenv("PI_WALLET_SEED", "")  # App Wallet Private Seed (Testnet)

# Fill in 10 real Pi UIDs below.
# Tip: Ask friends to open your testnet app once — their UID will be saved to DB.
# Then run: SELECT pi_uid FROM users WHERE auth_method='pi_network' AND pi_uid IS NOT NULL;
TARGET_UIDS = [
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 1
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 2
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 3
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 4
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 5
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 6
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 7
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 8
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 9
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # friend 10
]

AMOUNT_PER_USER = 0.1   # Pi to send each user (minimum on testnet)
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
        print("❌ Missing PI_API_KEY. Set it in environment or fill TESTNET_API_KEY above.")
        sys.exit(1)

    if not TESTNET_WALLET_SEED:
        print("❌ Missing PI_WALLET_SEED. Get it from Pi Developer Portal → Testnet Wallet.")
        sys.exit(1)

    real_uids = [uid for uid in TARGET_UIDS if uid and not uid.startswith("#")]
    if len(real_uids) < 10:
        print(f"❌ Need 10 UIDs in TARGET_UIDS, currently have {len(real_uids)}.")
        print("   Ask friends to log in to your testnet app, then get their UIDs from DB:")
        print("   SELECT pi_uid FROM users WHERE auth_method='pi_network' AND pi_uid IS NOT NULL;")
        sys.exit(1)

    return real_uids

# ============================================================
# MAIN
# ============================================================

def run():
    print("=" * 55)
    print("  PI CryptoMind — Testnet A2U Bootstrap")
    print("=" * 55)

    real_uids = check_safety()

    try:
        from pi_python import PiNetwork
    except ImportError:
        print("❌ pi-python not installed. Run: pip install pi-python")
        sys.exit(1)

    pi = PiNetwork()
    pi.initialize(TESTNET_API_KEY, TESTNET_WALLET_SEED, "Pi Testnet")
    print(f"✅ Pi SDK initialized (Testnet)\n")

    results = {"success": [], "failed": []}

    for i, uid in enumerate(real_uids[:10], 1):
        print(f"[{i}/10] Sending {AMOUNT_PER_USER}π → UID: {uid[:16]}...")
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

        # Pi requires sequential payments — wait between each
        if i < 10:
            time.sleep(2)

    print("\n" + "=" * 55)
    print(f"  Results: {len(results['success'])}/10 successful")
    if results["failed"]:
        print(f"  Failed UIDs:")
        for f in results["failed"]:
            print(f"    - {f['uid'][:16]}... : {f['error']}")

    if len(results["success"]) >= 10:
        print("\n🎉 Done! You can now apply for the Mainnet App Wallet.")
        print("   Set TESTNET_A2U_DONE=true to prevent re-running.")
    print("=" * 55)


if __name__ == "__main__":
    run()
