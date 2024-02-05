from flask import Blueprint, render_template
from ..services import TransactionService
from webargs.flaskparser import use_args
from ..services import BalanceService
from ..services import AddressService
from ..services import TokenService
from ..services import BlockService
from flask import redirect, url_for
from webargs import fields
from pony import orm
from .. import utils
import math

from datetime import timedelta
from ..models import Index, Transfer, Transaction, Balance, Peer
from ..models import ChartTransactions, ChartVolume

blueprint = Blueprint("explorer", __name__)


@blueprint.route("/")
@orm.db_session
def overview():
    latest = BlockService.latest_block()
    supply_data = utils.supply(latest.height)
    supply = utils.amount(supply_data["supply"])

    transactions = TransactionService.transactions_frontend(pagesize=10)
    # transactions = []

    start = latest.created - timedelta(hours=24)

    diff = utils.make_request("getmininginfo")

    pow_diff = 0
    pos_diff = 0

    if not diff["error"]:
        pow_diff = diff["result"]["difficulty"]["proof-of-work"]
        pos_diff = diff["result"]["difficulty"]["proof-of-stake"]

    stats = {
        "volume": round(
            orm.select(
                t.amount for t in Transaction if t.created > start
            ).sum(),
            2,
        ),
        "count": {
            "transactions": Transaction.select(
                lambda t: t.created > start
            ).count(distinct=False),
            "addresses": Balance.select(lambda b: b.amount > 0).count(
                distinct=False
            ),
        },
        "supply": supply,
        "diff": {
            "pow": round(pow_diff, 6),
            "pos": round(pos_diff, 4),
        },
    }

    blocks = BlockService.blocks(pagesize=10)

    return render_template(
        "pages/overview.html",
        latest=latest,
        blocks=blocks,
        transactions=transactions,
        stats=stats,
    )


@blueprint.route("/list/blocks/", defaults={"page": 1})
@blueprint.route("/list/blocks/<int:page>")
@orm.db_session
def blocks(page):
    size = 30
    latest = BlockService.latest_block()
    total = math.ceil(latest.height / size)

    blocks = BlockService.blocks(page, size)
    pagination = utils.pagination("explorer.blocks", page, size, total)

    return render_template(
        "pages/blocks.html", pagination=pagination, blocks=blocks
    )


@blueprint.route("/get/block/<string:blockhash>", defaults={"page": 1})
@blueprint.route("/get/block/<string:blockhash>/<int:page>")
@orm.db_session
def block(blockhash, page):
    size = 10

    if block := BlockService.get_by_hash(blockhash):
        transactions = block.txs.page(page, pagesize=size)

        total = math.ceil(block.tx_count / size)
        pagination = utils.pagination("explorer.block", page, size, total)

        title = f"Block #{block.height}"

        return render_template(
            "pages/block.html",
            block=block,
            transactions=transactions,
            pagination=pagination,
            title=title,
        )

    return render_template("pages/404.html")


@blueprint.route("/list/transactions", defaults={"page": 1})
@blueprint.route("/list/transactions/<int:page>")
@orm.db_session
def transactions(page):
    size = 100

    transactions_data = TransactionService.transactions(page, size)
    transactions = []

    for entry in transactions_data:
        transaction = entry[0]
        amount = entry[1]

        transactions.append(
            {
                "height": transaction.height,
                "blockhash": (
                    transaction.block.blockhash if transaction.block else None
                ),
                "timestamp": transaction.created.timestamp(),
                "created": transaction.created,
                "block": transaction.block,
                "txid": transaction.txid,
                "amount": amount,
            }
        )

    count = TransactionService.count()
    total = math.ceil(count / size)

    pagination = utils.pagination("explorer.transactions", page, size, total)

    return render_template(
        "pages/transactions.html",
        pagination=pagination,
        transactions=transactions,
    )


@blueprint.route("/get/transaction/<string:txid>")
@orm.db_session
def transaction(txid):
    title = f"Transaction {txid[:16]}..."
    transaction = TransactionService.get_by_txid(txid)

    if transaction:
        return render_template(
            "pages/transaction.html", transaction=transaction, title=title
        )

    return render_template("pages/404.html")


@blueprint.route("/get/address/<string:address>", defaults={"page": 1})
@blueprint.route("/get/address/<string:address>/<int:page>")
@orm.db_session
def address(address, page):
    size = 10

    if address := AddressService.get_by_address(address):
        index = address.index.order_by(orm.desc(Index.created)).page(
            page, pagesize=size
        )
        transactions = []

        for entry in index:
            transactions.append(entry.transaction)

        total = math.ceil(address.txcount / size)
        pagination = utils.pagination("explorer.address", page, size, total)

        title = f"Address {address.address}"

        return render_template(
            "pages/address.html",
            address=address,
            transactions=transactions,
            pagination=pagination,
            title=title,
        )

    return render_template("pages/404.html")


@blueprint.route("/list/tokens", defaults={"page": 1})
@blueprint.route("/list/tokens/<int:page>")
@orm.db_session
def tokens(page):
    size = 100

    tokens = TokenService.list(page, size)
    count = TokenService.count()
    total = math.ceil(count / size)

    pagination = utils.pagination("explorer.tokens", page, size, total)

    return render_template(
        "pages/tokens.html", pagination=pagination, tokens=tokens
    )


@blueprint.route("/list/holders", defaults={"page": 1})
@blueprint.route("/list/holders/<int:page>")
@orm.db_session
def holders(page):
    size = 100

    balances = BalanceService.holders(page, size)
    count = BalanceService.holders_count()
    total = math.ceil(count / size)

    pagination = utils.pagination("explorer.holders", page, size, total)

    return render_template(
        "pages/holders.html",
        pagination=pagination,
        balances=balances,
        current_page=page,
        page_size=size,
    )


@blueprint.route("/get/map")
@orm.db_session
def peers_map():
    peers = Peer.select()
    return render_template("pages/map.html", peers=peers)


@blueprint.route("/get/token/<string:address>", defaults={"page": 1})
@blueprint.route("/get/token/<string:address>/<int:page>")
@orm.db_session
def token(address, page):
    if token := TokenService.get_by_address(address):
        title = f"Token {token.ticker}"

        size = 100
        total = math.ceil(token.txcount / size)

        transactions = orm.select(
            t.transaction for t in Transfer if t.token == token
        ).page(page, size)

        pagination = utils.pagination("explorer.token", page, size, total)

        return render_template(
            "pages/token.html",
            pagination=pagination,
            transactions=transactions,
            # transfers=transfers,
            token=token,
            title=title,
        )

    return render_template("pages/404.html")


@blueprint.route("/search")
@use_args({"query": fields.Str(required=True)}, location="query")
@orm.db_session
def search(args):
    if args["query"].isdigit():
        if block := BlockService.get_by_height(args["query"]):
            return redirect(
                url_for(
                    "explorer.block", blockhash=block.blockhash, _external=True
                )
            )

    else:
        if len(args["query"]) == 64:
            if block := BlockService.get_by_hash(args["query"]):
                return redirect(
                    url_for(
                        "explorer.block",
                        blockhash=block.blockhash,
                        _external=True,
                    )
                )

            return redirect(
                url_for(
                    "explorer.transaction", txid=args["query"], _external=True
                )
            )

        elif len(args["query"]) == 40:
            return redirect(
                url_for("explorer.token", address=args["query"], _external=True)
            )

        elif len(args["query"]) == 34:
            return redirect(
                url_for(
                    "explorer.address", address=args["query"], _external=True
                )
            )

    return redirect(url_for("explorer.overview", _external=True))


@blueprint.route("/tx/<string:txid>")
def tx_redirect(txid):
    return redirect(url_for("explorer.transaction", txid=txid, _external=True))


@blueprint.route("/data/chart")
@orm.db_session
def chart():
    chart_transactions = (
        ChartTransactions.select()
        .order_by(orm.desc(ChartTransactions.time))
        .limit(30)
    )

    chart_volume = (
        ChartVolume.select().order_by(orm.desc(ChartVolume.time)).limit(30)
    )

    chart_data = {
        "transactions": {
            "labels": [
                tx.time.strftime("%d-%m-%Y") for tx in chart_transactions
            ],
            "data": [tx.value for tx in chart_transactions],
        },
        "volume": {
            "labels": [
                volume.time.strftime("%d-%m-%Y") for volume in chart_volume
            ],
            "data": [volume.value for volume in chart_volume],
        },
    }

    return utils.response(chart_data)


@blueprint.route("/data/peers")
@orm.db_session
def peers():
    peers = []

    for peer in Peer.select():
        peers.append(
            {
                "last": peer.last,
                "address": peer.address,
                "country": peer.country,
                "subver": peer.subver,
                "height": peer.height,
                "code": peer.code,
                "city": peer.city,
                "port": peer.port,
                "lat": peer.lat,
                "lon": peer.lon,
            }
        )

    return utils.response(peers)


@blueprint.route("/api")
def api():
    return render_template("api.html")
