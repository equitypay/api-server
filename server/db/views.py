from ..methods.transaction import Transaction as NodeTransaction
from ..methods.general import General as NodeGeneral
from ..services import TransactionService
from webargs.flaskparser import use_args
from ..services import AddressService
from ..services import BlockService
from ..models import Transaction
from .args import broadcast_args
from .args import height_args
from datetime import datetime
from .args import page_args
from flask import Blueprint
from ..tools import display
from .. import utils
from pony import orm

db = Blueprint("db", __name__, url_prefix="/v2/")

@db.route("/latest", methods=["GET"])
@orm.db_session
def info():
    block = BlockService.latest_block()

    return utils.response({
        "time": block.created.timestamp(),
        "blockhash": block.blockhash,
        "height": block.height,
        "chainwork": block.chainwork,
        "difficulty": block.difficulty,
        "reward": float(block.reward)
    })

@db.route("/transactions", methods=["GET"])
@use_args(page_args, location="query")
@orm.db_session
def transactions(args):
    transactions = TransactionService.transactions(args["page"])
    result = []

    for entry in transactions:
        transaction = entry[0]
        amount = entry[1]

        result.append({
            "height": transaction.height,
            "blockhash": transaction.block.blockhash,
            "timestamp": transaction.created.timestamp(),
            "txhash": transaction.txid,
            "amount": float(amount)
        })

    return utils.response(result)

@db.route("/blocks", methods=["GET"])
@use_args(page_args, location="query")
@orm.db_session
def blocks(args):
    blocks = BlockService.blocks(args["page"])
    result = []

    for block in blocks:
        result.append({
            "height": block.height,
            "blockhash": block.blockhash,
            "timestamp": block.created.timestamp(),
            "tx": len(block.transactions)
        })

    return utils.response(result)

@db.route("/block/<string:bhash>", methods=["GET"])
@orm.db_session
def block(bhash):
    block = BlockService.get_by_hash(bhash)

    if block:
        return utils.response({
            "reward": float(block.reward),
            "signature": block.signature,
            "blockhash": block.blockhash,
            "height": block.height,
            "tx": len(block.transactions),
            "timestamp": block.created.timestamp(),
            "difficulty": block.difficulty,
            "merkleroot": block.merkleroot,
            "chainwork": block.chainwork,
            "version": block.version,
            "weight": block.weight,
            "stake": block.stake,
            "nonce": block.nonce,
            "size": block.size,
            "bits": block.bits
        })

    return utils.dead_response("Block not found"), 404

@db.route("/block/<string:bhash>/transactions", methods=["GET"])
@use_args(page_args, location="query")
@orm.db_session
def block_transactions(args, bhash):
    block = BlockService.get_by_hash(bhash)

    if block:
        transactions = block.transactions.page(args["page"])
        result = []

        for transaction in transactions:
            result.append(transaction.display())

        return utils.response(result)

    return utils.dead_response("Block not found"), 404

@db.route("/transaction/<string:txid>", methods=["GET"])
@orm.db_session
def transaction(txid):
    transaction = TransactionService.get_by_txid(txid)

    if transaction:
        return utils.response(transaction.display())

    data = NodeTransaction.info(txid)
    if not data["error"]:
        result = display.tx_to_db(data)
        return utils.response(result)

    return utils.dead_response("Transaction not found"), 404

@db.route("/history/<string:address>", methods=["GET"])
@use_args(page_args, location="query")
@orm.db_session
def history(args, address):
    address = AddressService.get_by_address(address)
    result = []

    if address:
        transactions = address.transactions.order_by(
            orm.desc(Transaction.id)
        ).page(args["page"], pagesize=100)

        for transaction in transactions:
            result.append(transaction.display())

    return utils.response(result)

@db.route("/stats/<string:address>", methods=["GET"])
@orm.db_session
def count(address):
    address = AddressService.get_by_address(address)
    transactions = 0

    if address:
        transactions = len(address.transactions)

    return utils.response({
        "transactions": transactions
    })

@db.route("/richlist", methods=["GET"])
@use_args(page_args, location="query")
@orm.db_session
def richlist(args):
    addresses = AddressService.richlist(args["page"])
    result = []

    for entry in addresses:
        result.append({
            "address": entry[0].address,
            "balance": float(entry[1])
        })

    return utils.response(result)

@db.route("/chart", methods=["GET"])
@orm.db_session
def chart():
    data = BlockService.chart()
    result = {}

    for entry in data:
        result[entry[0]] = entry[1]

    return utils.response(result)

@db.route("/balance/<string:address>", methods=["GET"])
@orm.db_session
def test(address):
    address = AddressService.get_by_address(address)
    result = {}

    if address:
        result = {
            "balance": float(address.balances.amount),
        }

    return utils.response(result)

@db.route("/mempool", methods=["GET"])
@orm.db_session
def mempool():
    data = NodeGeneral.mempool()

    if not data["error"]:
        mempool = data["result"]["tx"]
        new = []

        for txid in mempool:
            tx = NodeTransaction.info(txid)
            new.append(display.tx_to_db(tx))

        data["result"]["tx"] = new

    return data

@db.route("/broadcast", methods=["POST"])
@use_args(broadcast_args, location="json")
def broadcast(args):
    return NodeTransaction.broadcast(args["raw"])

@db.route("/txs/<string:address>", methods=["GET"])
@use_args(height_args, location="query")
@orm.db_session
def txs(args, address):
    address = AddressService.get_by_address(address)
    result = []
    count = 0

    if address:
        transactions = address.transactions.order_by(
            orm.desc(Transaction.id)
        )

        count = transactions.count()

        if args["start"]:
            start = datetime.fromtimestamp(args["start"])
            transactions = transactions.filter(lambda t: t.created >= start)

        if args["finish"]:
            finish = datetime.fromtimestamp(args["finish"])
            transactions = transactions.filter(lambda t: t.created <= finish)

        for transaction in transactions:
            result.append(transaction.txid)

    return utils.response({
        "txcount": count,
        "tx": result
    })
