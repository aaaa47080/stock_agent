# -*- coding: utf-8 -*-
"""
For more information visit https://github.com/pi-apps/pi-python
"""

import requests
import json
import stellar_sdk as s_sdk

class PiNetwork:

    api_key = ""
    client = ""
    account = ""
    base_url = ""
    from_address = ""
    open_payments = {}
    network = ""
    server = ""
    keypair = ""
    fee = ""

    def initialize(self, api_key, wallet_private_key, network):
        try:
            if not self.validate_private_seed_format(wallet_private_key):
                print("No valid private seed!")
            self.api_key = api_key
            self.load_account(wallet_private_key, network)
            self.base_url = "https://api.minepi.com"
            self.open_payments = {}
            self.network = network
            self.fee = self.server.fetch_base_fee()
        except:
            return False

    def get_balance(self):
        try:
            balances = self.server.accounts().account_id(self.keypair.public_key).call()["balances"]
            for i in balances:
                if i["asset_type"] == "native":
                    return float(i["balance"])
            return 0
        except:
            return 0

    def get_payment(self, payment_id):
        url = self.base_url + "/v2/payments/" + payment_id
        re = requests.get(url, headers=self.get_http_headers())
        return self.handle_http_response(re)

    def create_payment(self, payment_data):
        try:
            balances = self.server.accounts().account_id(self.keypair.public_key).call()["balances"]
            for i in balances:
                if i["asset_type"] == "native":
                    if (float(payment_data["amount"]) + (float(self.fee) / 10000000)) > float(i["balance"]):
                        return ""
                    break

            obj = json.dumps({'payment': payment_data})
            url = self.base_url + "/v2/payments"
            res = requests.post(url, data=obj, json=obj, headers=self.get_http_headers())
            parsed_response = self.handle_http_response(res)

            if 'error' in parsed_response:
                identifier = parsed_response['payment']["identifier"]
                identifier_data = parsed_response['payment']
            else:
                identifier = parsed_response["identifier"]
                identifier_data = parsed_response

            self.open_payments[identifier] = identifier_data
            return identifier
        except Exception as e:
            print(f"create_payment error: {e}")
            return ""

    def submit_payment(self, payment_id, pending_payment=False):
        if payment_id not in self.open_payments:
            return False
        payment = self.open_payments[payment_id]

        balances = self.server.accounts().account_id(self.keypair.public_key).call()["balances"]
        for i in balances:
            if i["asset_type"] == "native":
                if (float(payment["amount"]) + (float(self.fee)/10000000)) > float(i["balance"]):
                    return ""
                break

        self.set_horizon_client(payment["network"])
        transaction = self.build_a2u_transaction(payment)
        txid = self.submit_transaction(transaction)
        if payment_id in self.open_payments:
            del self.open_payments[payment_id]
        return txid

    def complete_payment(self, identifier, txid):
        obj = json.dumps({"txid": txid} if txid else {})
        url = self.base_url + "/v2/payments/" + identifier + "/complete"
        re = requests.post(url, data=obj, json=obj, headers=self.get_http_headers())
        return self.handle_http_response(re)

    def cancel_payment(self, identifier):
        obj = json.dumps({})
        url = self.base_url + "/v2/payments/" + identifier + "/cancel"
        re = requests.post(url, data=obj, json=obj, headers=self.get_http_headers())
        return self.handle_http_response(re)

    def get_incomplete_server_payments(self):
        url = self.base_url + "/v2/payments/incomplete_server_payments"
        re = requests.get(url, headers=self.get_http_headers())
        res = self.handle_http_response(re)
        if not res:
            res = {"incomplete_server_payments": []}
        return res["incomplete_server_payments"]

    def get_http_headers(self):
        return {'Authorization': "Key " + self.api_key, "Content-Type": "application/json"}

    def handle_http_response(self, re):
        try:
            result = re.json()
            result_dict = json.loads(str(json.dumps(result)))
            print("HTTP-Response: " + str(re.status_code))
            print("HTTP-Response Data: " + str(result_dict))
            return result_dict
        except:
            return False

    def set_horizon_client(self, network):
        self.client = self.server

    def load_account(self, private_seed, network):
        self.keypair = s_sdk.Keypair.from_secret(private_seed)
        if network == "Pi Network":
            horizon = "https://api.mainnet.minepi.com"
        else:
            horizon = "https://api.testnet.minepi.com"
        self.server = s_sdk.Server(horizon)
        self.account = self.server.load_account(self.keypair.public_key)

    def build_a2u_transaction(self, transaction_data):
        amount = str(transaction_data["amount"])
        fee = self.fee
        to_address = transaction_data["to_address"]
        memo = transaction_data["identifier"]
        transaction = (
            s_sdk.TransactionBuilder(
                source_account=self.account,
                network_passphrase=self.network,
                base_fee=fee,
            )
            .add_text_memo(memo)
            .append_payment_op(to_address, s_sdk.Asset.native(), amount)
            .set_timeout(180)
            .build()
        )
        return transaction

    def submit_transaction(self, transaction):
        transaction.sign(self.keypair)
        response = self.server.submit_transaction(transaction)
        txid = response["id"]
        return txid

    def validate_private_seed_format(self, seed):
        if not seed.upper().startswith("S"):
            return False
        elif len(seed) != 56:
            return False
        return True
