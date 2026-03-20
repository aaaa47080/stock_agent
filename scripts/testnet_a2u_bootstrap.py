# -*- coding: utf-8 -*-
"""
Testnet A2U Bootstrap Script
=============================
PURPOSE: Send 0.1pi to 10 unique Pi users on testnet to satisfy
         Pi Network's "App to User transactions to 10 unique wallets"
         requirement for Mainnet App Wallet application.

USAGE:
  PI_API_KEY=<testnet_api_key> PI_WALLET_SEED=<testnet_wallet_seed> python scripts/testnet_a2u_bootstrap.py

IMPORTANT:
  - This script is for TESTNET ONLY
  - Run ONCE manually, never runs automatically
  - Will NOT run if TESTNET_A2U_DONE=true in environment
"""

import os
import sys
import time

# Fix Windows console encoding
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Allow importing pi_python.py from the same scripts/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# CONFIG
# ============================================================

TESTNET_API_KEY = os.getenv("PI_API_KEY", "")
TESTNET_WALLET_SEED = os.getenv("PI_WALLET_SEED", "")

# UIDs from production DB (real Pi users who logged in to the app)
TARGET_UIDS = [
    # Already successful - skip these two:
    # "de596108-bd78-46cc-9948-4b8353ff638c",  # OK a1031737
    # "b872c933-5615-4819-b5bb-748d5cde17f1",  # OK a8031737
    "10f4ac13-fc62-452e-8cda-1c6c648fdc4a",  # 2717Fhj21jxn
    "c9c13c0a-e0c1-428f-8356-b795247eed39",  # 272id1717A
    "13b802c4-e37c-4d81-b860-ad35d3588672",  # a228md27
    "03930461-49b8-46aa-91d5-a3a8ef4acf2a",  # aaa47080
    "a2f7effa-a864-4dab-bbeb-fd8963165ab1",  # tyc60718
    # "dc7202e3-1d97-4f4a-8c09-c11c48267535",  # SKIP aaaa47080 - testnet wallet not funded
    "db8c4c54-184e-42bc-88a6-6ff0795279aa",  # ghi17279
    "202a014c-9253-4961-a6e6-c568ebd1095f",  # Sgh2738h
    "a8141502-2d0a-4dc4-ba49-cd2a00103646",  # bnu2728as
]

AMOUNT_PER_USER = 0.1
MEMO = "PI CryptoMind testnet A2U bootstrap"

# ============================================================
# SAFETY CHECKS
# ============================================================


def check_safety():
    if os.getenv("TESTNET_A2U_DONE", "").lower() == "true":
        print("[DONE] TESTNET_A2U_DONE=true - already completed, skipping.")
        sys.exit(0)

    if os.getenv("ENVIRONMENT", "development").lower() in ["production", "prod"]:
        print("[BLOCKED] Cannot run on production environment.")
        sys.exit(1)

    if not TESTNET_API_KEY:
        print("[ERROR] Missing PI_API_KEY.")
        sys.exit(1)

    if not TESTNET_WALLET_SEED:
        print("[ERROR] Missing PI_WALLET_SEED.")
        sys.exit(1)


# ============================================================
# MAIN
# ============================================================


def run():
    print("=" * 55)
    print("  PI CryptoMind - Testnet A2U Bootstrap")
    print("=" * 55)

    check_safety()

    try:
        from pi_python import PiNetwork
    except ImportError:
        print("[ERROR] pi_python.py not found in scripts/ directory.")
        sys.exit(1)

    pi = PiNetwork()
    pi.initialize(TESTNET_API_KEY, TESTNET_WALLET_SEED, "Pi Testnet")
    print("[OK] Pi SDK initialized (Testnet)\n")

    results = {"success": [], "failed": []}

    total = len(TARGET_UIDS)
    for i, uid in enumerate(TARGET_UIDS, 1):
        print(f"[{i}/{total}] Sending {AMOUNT_PER_USER}pi -> {uid[:16]}...")
        try:
            payment_data = {
                "amount": AMOUNT_PER_USER,
                "memo": MEMO,
                "metadata": {"bootstrap": True, "index": i},
                "uid": uid,
            }

            payment_id = pi.create_payment(payment_data)
            print(f"       payment_id: {payment_id}")
            if not payment_id:
                raise Exception(
                    "create_payment returned empty - check balance or API key"
                )

            txid = pi.submit_payment(payment_id)
            print(f"       txid: {txid}")

            payment = pi.complete_payment(payment_id, txid)
            status = (
                payment.get("status", "unknown")
                if isinstance(payment, dict)
                else str(payment)
            )
            print(f"       [OK] Done - status: {status}")
            results["success"].append(uid)

        except Exception as e:
            print(f"       [FAIL] {e}")
            results["failed"].append({"uid": uid, "error": str(e)})

        if i < total:
            time.sleep(3)

    print("\n" + "=" * 55)
    print(f"  Results: {len(results['success'])}/10 successful")
    if results["failed"]:
        print("  Failed:")
        for f in results["failed"]:
            print(f"    - {f['uid'][:16]}... : {f['error']}")

    if len(results["success"]) >= 10:
        print("\n[SUCCESS] Done! You can now apply for the Mainnet App Wallet.")
    print("=" * 55)


if __name__ == "__main__":
    run()
