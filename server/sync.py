from .methods.transaction import Transaction
from .services import TransactionService
from .services import BalanceService
from .methods.general import General
from .services import AddressService
from .services import OutputService
from .services import InputService
from .services import BlockService
from .services import IndexService
from .methods.block import Block
from datetime import datetime
from pony import orm
from . import utils

from .models import Token, TokenBalance, Transfer

TRANSFER_TOPIC = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

def log_block(message, block, tx=[]):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time = block.created.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} {message}: hash={block.blockhash} height={block.height} tx={len(tx)} date='{time}'")

def log_message(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} {message}")

@orm.db_session
def rollback_blocks(height):
    latest_block = BlockService.latest_block()

    while latest_block.height >= height:
        log_block("Found reorg", latest_block)

        reorg_block = latest_block
        latest_block = reorg_block.previous_block

        reorg_block.delete()
        orm.commit()

    log_message("Finised rollback")

@orm.db_session
def sync_blocks():
    if not BlockService.latest_block():
        data = Block.height(0)["result"]
        created = datetime.fromtimestamp(data["time"])
        signature = data["signature"] if "signature" in data else None

        block = BlockService.create(
            utils.amount(data["reward"]), data["hash"], data["height"], created,
            data["difficulty"], data["merkleroot"], data["chainwork"],
            data["version"], data["weight"], data["stake"], data["nonce"],
            data["size"], data["bits"], signature
        )

        log_block("Genesis block", block)

        orm.commit()

    current_height = General.current_height()
    latest_block = BlockService.latest_block()

    log_message(f"Current node height: {current_height}, db height: {latest_block.height}")

    while latest_block.blockhash != Block.blockhash(latest_block.height):
        log_block("Found reorg", latest_block)

        reorg_block = latest_block
        latest_block = reorg_block.previous_block

        reorg_block.delete()
        orm.commit()

    for height in range(latest_block.height + 1, current_height + 1):
        block_data = Block.height(height)["result"]
        created = datetime.fromtimestamp(block_data["time"])
        signature = block_data["signature"] if "signature" in block_data else None

        block = BlockService.create(
            utils.amount(block_data["reward"]), block_data["hash"], block_data["height"], created,
            block_data["difficulty"], block_data["merkleroot"], block_data["chainwork"],
            block_data["version"], block_data["weight"], block_data["stake"], block_data["nonce"],
            block_data["size"], block_data["bits"], signature
        )

        block.previous_block = latest_block

        log_block("New block", block, block_data["tx"])

        for index, txid in enumerate(block_data["tx"]):
            if block.stake and index == 0:
                continue

            tx_data = Transaction.info(txid, False)["result"]
            created = datetime.fromtimestamp(tx_data["time"])
            coinbase = block.stake is False and index == 0
            coinstake = block.stake and index == 1

            transaction = TransactionService.create(
                utils.amount(tx_data["amount"]), tx_data["txid"],
                created, tx_data["locktime"], tx_data["size"], block,
                coinbase, coinstake
            )

            for vin in tx_data["vin"]:
                if "coinbase" in vin:
                    continue

                prev_tx = TransactionService.get_by_txid(vin["txid"])
                prev_out = OutputService.get_by_prev(prev_tx, vin["vout"])

                prev_out.address.transactions.add(transaction)
                balance = BalanceService.get(prev_out.address)
                balance.amount -= prev_out.amount

                IndexService.create(prev_out.address, transaction)

                InputService.create(
                    vin["sequence"], vin["vout"], transaction, prev_out
                )

            for vout in tx_data["vout"]:
                if vout["scriptPubKey"]["type"] in ["nonstandard", "nulldata"]:
                    continue

                if "addresses" not in vout["scriptPubKey"]:
                    continue

                if len(vout["scriptPubKey"]["addresses"]) == 0:
                    continue

                amount = utils.amount(vout["valueSat"])
                script = vout["scriptPubKey"]["addresses"][0]

                if not (address := AddressService.get_by_address(script)):
                    address = AddressService.create(script)

                address.transactions.add(transaction)

                IndexService.create(address, transaction)

                output = OutputService.create(
                    transaction, amount, vout["scriptPubKey"]["type"],
                    address, vout["scriptPubKey"]["hex"],
                    vout["n"]
                )

                if not (balance := BalanceService.get(address)):
                    balance = BalanceService.create(address)

                balance.amount += output.amount

            receipts = utils.make_request("gettransactionreceipt", [transaction.txid])

            for receipt in receipts["result"]:
                address_from = utils.hash160_to_address(receipt["from"])

                for contract in receipt["createdContracts"]:
                    contract_address = contract["address"]

                    data = utils.make_request("eqrc20info", [contract_address])
                    if data["error"]:
                        continue

                    if not (issuer := AddressService.get_by_address(address_from)):
                        issuer = AddressService.create(address_from)

                    IndexService.create(issuer, transaction)

                    info = data["result"]

                    token = Token(**{
                        "created": transaction.created,
                        "supply": float(info["supply"]),
                        "decimals": info["decimals"],
                        "address": contract_address,
                        "transaction": transaction,
                        "ticker": info["symbol"],
                        "name": info["name"],
                        "issuer": issuer
                    })

                    TokenBalance(**{
                        "amount": token.supply,
                        "address": issuer,
                        "token": token
                    })

                for log in receipt["log"]:
                    if not (token := Token.get(address=log["address"])):
                        continue

                    if len(log["topics"]) != 3:
                        continue

                    if log["topics"][0] != TRANSFER_TOPIC:
                        continue

                    receiver_hash160 = log["topics"][2][-40:]
                    address_to = utils.hash160_to_address(receiver_hash160)
                    raw_amount = int(log["data"], 16)
                    amount = utils.amount(raw_amount, token.decimals)

                    if not (sender := AddressService.get_by_address(address_from)):
                        sender = AddressService.create(address_from)

                    if not (receiver := AddressService.get_by_address(address_to)):
                        receiver = AddressService.create(address_to)

                    if not (sender_balance := TokenBalance.get(address=sender, token=token)):
                        sender_balance = TokenBalance(address=sender, token=token)

                    if not (receiver_balance := TokenBalance.get(address=receiver, token=token)):
                        receiver_balance = TokenBalance(address=receiver, token=token)

                    IndexService.create(sender, transaction)
                    IndexService.create(receiver, transaction)

                    transfer = Transfer(**{
                        "created": transaction.created,
                        "transaction": transaction,
                        "receiver": receiver,
                        "sender": sender,
                        "amount": amount,
                        "token": token
                    })

                    receiver_balance.amount += transfer.amount
                    sender_balance.amount -= transfer.amount

        latest_block = block
        orm.commit()
