from flask import Blueprint, render_template
from ..services import TransactionService
from webargs.flaskparser import use_args
from ..services import AddressService
from ..services import BlockService
from flask import redirect, url_for
from webargs import fields
from .. import utils
from pony import orm
import math

blueprint = Blueprint("explorer", __name__)

@blueprint.route("/")
@orm.db_session
def overview():
    latest = BlockService.latest_block()
    supply_data = utils.supply(latest.height)
    supply = utils.amount(supply_data["supply"])

    transactions_data = TransactionService.transactions(pagesize=10)
    transactions = []

    for entry in transactions_data:
        transaction = entry[0]
        amount = entry[1]

        transactions.append({
            "height": transaction.block.height,
            "blockhash": transaction.block.blockhash,
            "timestamp": transaction.block.created.timestamp(),
            "txid": transaction.txid,
            "amount": amount
        })

    blocks = BlockService.blocks(pagesize=10)

    return render_template(
        "pages/overview.html", latest=latest,
        supply=supply, blocks=blocks,
        transactions=transactions
    )

@blueprint.route("/e/blocks/", defaults={"page": 1})
@blueprint.route("/e/blocks/<int:page>")
@orm.db_session
def blocks(page):
    size = 30
    latest = BlockService.latest_block()
    total = math.ceil(latest.height / size)

    blocks = BlockService.blocks(page, size)
    pagination = utils.pagination(
        "explorer.blocks", page,
        size, total
    )

    return render_template(
        "pages/blocks.html", pagination=pagination,
        blocks=blocks
    )

@blueprint.route("/e/block/<string:blockhash>", defaults={"page": 1})
@blueprint.route("/e/block/<string:blockhash>/<int:page>")
@orm.db_session
def block(blockhash, page):
    size = 10

    if (block := BlockService.get_by_hash(blockhash)):
        transactions = block.txs.page(page, pagesize=size)

        total = math.ceil(block.tx_count / size)
        pagination = utils.pagination(
            "explorer.block", page,
            size, total
        )

        title = f"Block #{block.height}"

        return render_template(
            "pages/block.html", block=block,
            transactions=transactions,
            pagination=pagination,
            title=title
        )

    return render_template("pages/404.html")

@blueprint.route("/e/transactions", defaults={"page": 1})
@blueprint.route("/e/transactions/<int:page>")
@orm.db_session
def transactions(page):
    size = 100

    transactions_data = TransactionService.transactions(page, size)
    transactions = []

    for entry in transactions_data:
        transaction = entry[0]
        amount = entry[1]

        transactions.append({
            "height": transaction.block.height,
            "blockhash": transaction.block.blockhash,
            "timestamp": transaction.block.created.timestamp(),
            "block": transaction.block,
            "txid": transaction.txid,
            "amount": amount
        })

    count = TransactionService.count()
    total = math.ceil(count / size)

    pagination = utils.pagination(
        "explorer.transactions", page,
        size, total
    )

    return render_template(
        "pages/transactions.html", pagination=pagination,
        transactions=transactions
    )

@blueprint.route("/e/transaction/<string:txid>")
@orm.db_session
def transaction(txid):
    title = f"Transaction {txid[:16]}..."
    transaction = TransactionService.get_by_txid(txid)

    if transaction:
        return render_template(
            "pages/transaction.html",
            transaction=transaction,
            title=title
        )

    return render_template("pages/404.html")

@blueprint.route("/address/<string:address>", defaults={"page": 1})
@blueprint.route("/address/<string:address>/<int:page>")
@orm.db_session
def address(address, page):
    size = 10

    if (address := AddressService.get_by_address(address)):
        transactions = address.txs.page(page, pagesize=size)

        total = math.ceil(address.txcount / size)
        pagination = utils.pagination(
            "explorer.address", page,
            size, total
        )

        title = f"Address {address.address}"

        return render_template(
            "pages/address.html", address=address,
            transactions=transactions,
            pagination=pagination,
            title=title
        )

    return render_template("pages/404.html")

@blueprint.route("/search")
@use_args({"query": fields.Str(required=True)}, location="query")
@orm.db_session
def search(args):
    if args["query"].isdigit():
        if (block := BlockService.get_by_height(args["query"])):
            return redirect(url_for("explorer.block", blockhash=block.blockhash))

    else:
        if len(args["query"]) == 64:
            if (block := BlockService.get_by_hash(args["query"])):
                return redirect(url_for("explorer.block", blockhash=block.blockhash))

            return redirect(url_for("explorer.transaction", txid=args["query"]))

        elif len(args["query"]) == 34:
            return redirect(url_for("explorer.address", address=args["query"]))

    return redirect(url_for("explorer.home"))