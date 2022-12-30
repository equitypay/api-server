from bitcoinutils.transactions import Transaction, TxInput, TxOutput
from ..methods.transaction import Transaction as NodeTransaction
from bitcoinutils.keys import PrivateKey, P2pkhAddress
from ..methods.address import Address as NodeAddress
from ..models import Index, Output, Address
from webargs.flaskparser import use_args
from ..sync import process_transaction
from bitcoinutils.script import Script
from ..services import AddressService
from bitcoinutils.setup import setup
from webargs import fields, validate
from bitcoinutils import constants
from base58check import b58encode
from flask import Blueprint
from pony import orm
from .. import utils
import hashlib
import config

constants.NETWORK_SEGWIT_PREFIXES["mainnet"] = "eqpay"
constants.NETWORK_P2PKH_PREFIXES["mainnet"] = b"\x21"
constants.NETWORK_P2SH_PREFIXES["mainnet"] = b"\x3A"
constants.NETWORK_WIF_PREFIXES["mainnet"] = b"\x46"

blueprint = Blueprint("wallet", __name__, url_prefix="/wallet")

secret_args = {
    "secret": fields.Str(required=True),
    "salt": fields.Str(required=True)
}

send_args = {
    "secret": fields.Str(required=True),
    "salt": fields.Str(required=True),
    "amount": fields.Int(required=True),
    "destination": fields.Str(required=True),
    "fee": fields.Int(missing=config.default_fee)
}

history_args = {
    "size": fields.Int(missing=10, validate=validate.Range(min=1, max=100)),
    "page": fields.Int(missing=1, validate=validate.Range(min=1))
}

def to_wif(secret, salt):
    seed = hashlib.blake2b(
        str.encode(secret),
        key=str.encode(salt),
        digest_size=32
    ).digest()

    data = constants.NETWORK_WIF_PREFIXES["mainnet"] + seed
    data += b"\x01"

    data_hash = hashlib.sha256(hashlib.sha256(data).digest()).digest()
    checksum = data_hash[0:4]

    wif = b58encode(data + checksum)

    return wif.decode("utf-8")

def check_address(address):
    data = NodeAddress.balance(address)

    if data["error"]:
        return False

    return True

@blueprint.route("/address", methods=["POST"])
@use_args(secret_args, location="json")
def address(args):
    setup("mainnet")

    priv = PrivateKey(wif=to_wif(args["secret"], args["salt"]))
    pub = priv.get_public_key()
    address = pub.get_address()

    return utils.response({
        "address": address.to_string()
    })

@blueprint.route("/send", methods=["POST"])
@use_args(send_args, location="json")
@orm.db_session
def send(args):
    setup("mainnet")

    priv = PrivateKey(wif=to_wif(args["secret"], args["salt"]))
    pub = priv.get_public_key()
    address = pub.get_address()
    addr_str = address.to_string()

    dest = args["destination"]
    balance = NodeAddress.balance(addr_str)
    amount = args["amount"]
    fee = args["fee"]

    if balance["error"]:
        return balance

    if balance["result"]["balance"] < amount + fee:
        return utils.dead_response("Not enough balance for transaction")

    if not check_address(dest):
        return utils.dead_response("Invalid destination address")

    unspent = []

    funded = False
    send_total = 0
    page = 1

    if not (db_addres := Address.get(address=addr_str)):
        return utils.dead_response("No available UTXOs for transaction")

    while True:
        outputs_list = Output.select(
            lambda o: o.spent == False and o.address == db_addres
        ).order_by(
            orm.desc(Output.amount_raw)
        ).page(page, pagesize=100)

        if len(outputs_list) == 0:
            break

        for output in outputs_list:
            print(output.txid, output.n, output.amount_raw)
            print(output.spent)
            unspent.append({
                "value": output.amount_raw,
                "txid": output.txid,
                "index": output.n
            })

            send_total += output.amount_raw

            if send_total >= amount:
                funded = True
                break

        if funded:
            break

        page += 1

    if not funded:
        return utils.dead_response("No available UTXOs for transaction")

    txout = []
    txin = []
    total = 0

    for utxo in unspent:
        vin = TxInput(utxo["txid"], utxo["index"])

        txin.append(vin)
        total += utxo["value"]

    change = total - amount - fee

    target = P2pkhAddress(dest)

    txout.append(TxOutput((amount), target.to_script_pub_key()))
    txout.append(TxOutput((change), address.to_script_pub_key()))

    tx = Transaction(txin, txout)
    pubkey = pub.to_hex()

    for i in range(0, len(txin)):
        sig = priv.sign_input(tx, i, Script(
            [
                "OP_DUP", "OP_HASH160", address.to_hash160(),
                "OP_EQUALVERIFY", "OP_CHECKSIG"
            ])
        )

        txin[i].script_sig = Script([sig, pubkey])

    serialized = tx.serialize()

    print(serialized)

    broadcast = NodeTransaction.broadcast(
        serialized
    )

    if not broadcast["error"]:
        process_transaction(broadcast["result"])

    return broadcast

@blueprint.route("/history/<string:raw_address>", methods=["GET"])
@use_args(history_args, location="query")
@orm.db_session
def history(args, raw_address):
    result = {}
    transactions = []

    if (address := AddressService.get_by_address(raw_address)):
        index = address.index.order_by(
            orm.desc(Index.created)
        ).page(args["page"], pagesize=args["size"])

        for entry in index:
            tx_data = entry.transaction.display()

            result = {
                "category": "",
                "amount": 0,
                "timestamp": tx_data["timestamp"],
                "txid": tx_data["txid"],
            }

            inputs = {}
            outputs = {}

            for vin in tx_data["inputs"]:
                if vin["address"] not in inputs:
                    inputs[vin["address"]] = 0

                inputs[vin["address"]] += vin["amount"]

            for vout in tx_data["outputs"]:
                if vout["address"] not in outputs:
                    outputs[vout["address"]] = 0

                outputs[vout["address"]] += vout["amount"]
            
            if tx_data["coinbase"] or tx_data["coinstake"]:
                result["category"] = "reward"

                amount = 0

                if raw_address in inputs:
                    amount = outputs[raw_address] - inputs[raw_address]
                else:
                    amount = outputs[raw_address]

                result["amount"] = round(amount, 8)
                
            else:
                sent = {}
                received = {}

                for vin in inputs:
                    if vin not in sent:
                        sent[vin] = inputs[vin]

                for vout in outputs:
                    if vout in sent:
                        sent[vout] -= outputs[vout]

                    else:
                        received[vout] = outputs[vout]

                if raw_address in sent:
                    result["category"] = "send"
                    result["amount"] = -round(sent[raw_address], 8)

                else:
                    result["category"] = "receive"
                    result["amount"] = round(received[raw_address], 8)

            transactions.append(result)

    return {
        "transactions": transactions
    }

@blueprint.route("/fee", methods=["GET"])
def fee():
    return utils.response({
        "fee": config.default_fee
    })

def init(app):
    app.register_blueprint(blueprint, url_prefix="/wallet")
