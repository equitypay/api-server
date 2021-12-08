from .args import broadcast_args, unspent_args
from ..methods.transaction import Transaction
from .args import offset_args, range_args
from webargs.flaskparser import use_args
from ..methods.general import General
from ..methods.address import Address
from ..methods.block import Block
from .args import token_list_args
from flask import Blueprint
from .. import utils

rest = Blueprint("rest", __name__)

@rest.route("/info", methods=["GET"])
def info():
    return General.info()

@rest.route("/height/<int:height>", methods=["GET"])
@use_args(offset_args, location="query")
def height(args, height):
    data = Block.height(height)

    if data["error"] is None:
        data["result"]["tx"] = data["result"]["tx"][args["offset"]:args["offset"] + 10]

    return data

@rest.route("/hash/<int:height>", methods=["GET"])
def block_hash(height):
    return Block.get(height)

@rest.route("/range/<int:height>", methods=["GET"])
@use_args(range_args, location="query")
def block_range(args, height):
    if args["offset"] > 100:
        args["offset"] = 100

    result = Block.range(height, args["offset"])
    return utils.response(result)

@rest.route("/block/<string:bhash>", methods=["GET"])
@use_args(offset_args, location="query")
def block(args, bhash):
    data = Block.hash(bhash)

    if data["error"] is None:
        data["result"]["tx"] = data["result"]["tx"][args["offset"]:args["offset"] + 10]

    return data

@rest.route("/header/<string:bhash>", methods=["GET"])
def header(bhash):
    return Block.header(bhash)

@rest.route("/transaction/<string:thash>", methods=["GET"])
def transaction(thash):
    return Transaction.info(thash)

@rest.route("/balance/<string:address>", methods=["GET"])
def balance(address):
    return Address.balance(address)

@rest.route("/history/<string:address>", methods=["GET"])
@use_args(offset_args, location="query")
def history(args, address):
    data = Address().history(address)

    if data["error"] is None:
        data["result"]["tx"] = data["result"]["tx"][args["offset"]:args["offset"] + 10]

    return data

@rest.route("/mempool/<string:address>", methods=["GET"])
def mempool(address):
    return Address.mempool(address)

@rest.route("/unspent/<string:address>", methods=["GET"])
@use_args(unspent_args, location="query")
def unspent(args, address):
    return Address.unspent(address, args["amount"])

@rest.route("/mempool", methods=["GET"])
def mempool_info():
    return General.mempool()

@rest.route("/decode/<string:raw>", methods=["GET"])
def decode(raw):
    return Transaction.decode(raw)

@rest.route("/fee", methods=["GET"])
def fee():
    return General.fee()

@rest.route("/supply", methods=["GET"])
def supply():
    return utils.response(General.supply())

@rest.route("/broadcast", methods=["POST"])
@use_args(broadcast_args, location="form")
def broadcast(args):
    return Transaction.broadcast(args["raw"])
