from bitcoinutils.transactions import Transaction, TxInput, TxOutput
from ..methods.transaction import Transaction as NodeTransaction
from bitcoinutils.keys import PrivateKey, P2pkhAddress
from webargs.flaskparser import use_args
from bitcoinutils.script import Script
from ..methods.address import Address
from bitcoinutils.setup import setup
from bitcoinutils import constants
from base58check import b58encode
from flask import Blueprint
from webargs import fields
from .. import utils
import hashlib

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
    "fee": fields.Int(missing=10000000)
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
    data = Address.balance(address)

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
def send(args):
    setup("mainnet")

    priv = PrivateKey(wif=to_wif(args["secret"], args["salt"]))
    pub = priv.get_public_key()
    address = pub.get_address()
    addr_str = address.to_string()

    dest = args["destination"]
    balance = Address.balance(addr_str)
    amount = args["amount"]
    fee = args["fee"]

    if balance["error"]:
        return balance

    if balance["result"]["balance"] < amount + fee:
        return utils.dead_response("Not enough balance for transaction")

    unspent = Address.unspent(addr_str, amount)

    if unspent["error"]:
        return unspent

    if len(unspent["result"]) == 0:
        return utils.dead_response("No available UTXOs for transaction")

    if not check_address(dest):
        return utils.dead_response("Invalid destination address")

    txout = []
    txin = []
    total = 0

    for utxo in unspent["result"]:
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

    return NodeTransaction.broadcast(
        tx.serialize()
    )

def init(app):
    app.register_blueprint(blueprint, url_prefix="/wallet")
