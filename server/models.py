from datetime import datetime
from decimal import Decimal
from pony import orm
from . import utils
import config

MEMPOOL_HEIGHT = -1

db = orm.Database(**config.db)


class Peer(db.Entity):
    _table_ = "chain_peers"

    last = orm.Required(datetime, default=datetime.utcnow)
    country = orm.Required(str)
    address = orm.Required(str)
    subver = orm.Required(str)
    height = orm.Required(int)
    lat = orm.Required(float)
    lon = orm.Required(float)
    port = orm.Required(int)
    city = orm.Required(str)
    code = orm.Required(str)


class Index(db.Entity):
    _table_ = "chain_transaciton_index"

    transaction = orm.Required("Transaction")
    address = orm.Required("Address")
    created = orm.Required(datetime)

    orm.composite_index(address, transaction)


class Token(db.Entity):
    _table_ = "chain_tokens"

    supply = orm.Required(Decimal, precision=20, scale=8)
    transaction = orm.Required("Transaction")
    address = orm.Required(str, index=True)
    issuer = orm.Required("Address")
    created = orm.Required(datetime)
    decimals = orm.Required(int)
    ticker = orm.Required(str)
    name = orm.Required(str)

    selected = orm.Required(bool, default=False)
    hidden = orm.Required(bool, default=False)

    balances = orm.Set("TokenBalance")
    transfers = orm.Set("Transfer")

    @property
    def txcount(self):
        return self.transfers.count()

    @property
    def holders(self):
        balances = TokenBalance.select(lambda b: b.token == self)
        balances = balances.filter(lambda b: b.amount > 0)
        return balances.count(distinct=False)


class TokenBalance(db.Entity):
    _table_ = "chain_token_balances"

    amount = orm.Required(Decimal, precision=20, scale=8, default=0)
    address = orm.Required("Address")
    token = orm.Required("Token")


class Transfer(db.Entity):
    _table_ = "chain_transfers"

    amount = orm.Required(Decimal, precision=20, scale=8, default=0)
    transaction = orm.Required("Transaction")
    receiver = orm.Required("Address")
    sender = orm.Required("Address")
    created = orm.Required(datetime)
    token = orm.Required("Token")


class Block(db.Entity):
    _table_ = "chain_blocks"

    reward = orm.Required(Decimal, precision=20, scale=8)
    signature = orm.Optional(str, nullable=True)
    blockhash = orm.Required(str, index=True)
    height = orm.Required(int, index=True)
    created = orm.Required(datetime)
    difficulty = orm.Required(float)
    merkleroot = orm.Required(str)
    chainwork = orm.Required(str)
    version = orm.Required(int)
    weight = orm.Required(int)
    stake = orm.Required(bool)
    nonce = orm.Required(int, size=64)
    size = orm.Required(int)
    bits = orm.Required(str)

    previous_block = orm.Optional("Block")
    transactions = orm.Set("Transaction")
    next_block = orm.Optional("Block")

    @property
    def confirmations(self):
        if self.height == MEMPOOL_HEIGHT:
            return 0

        latest_blocks = Block.select().order_by(orm.desc(Block.height)).first()

        return latest_blocks.height - self.height + 1

    @property
    def tx_count(self):
        return self.transactions.count()

    @property
    def timestamp(self):
        return int(self.created.timestamp())

    @property
    def txs(self):
        transactions = self.transactions.order_by(1)
        return transactions


class Transaction(db.Entity):
    _table_ = "chain_transactions"

    amount = orm.Required(Decimal, precision=20, scale=8)
    coinstake = orm.Required(bool, default=False)
    coinbase = orm.Required(bool, default=False)
    txid = orm.Required(str, index=True)
    height = orm.Required(int, size=64)
    created = orm.Required(datetime)
    locktime = orm.Required(int)
    size = orm.Required(int)

    transfers = orm.Set("Transfer")
    block = orm.Optional("Block")
    outputs = orm.Set("Output")
    inputs = orm.Set("Input")

    created_tokens = orm.Set("Token", reverse="transaction")
    addresses = orm.Set("Address")

    index = orm.Set("Index")

    def before_delete(self):
        # Reverse this transaction's contribution to the daily charts. Without
        # this the counters only ever grow: a reorg deletes the orphaned
        # transactions but their increments stay behind, and the replacement
        # chain then counts the very same transactions a second time.
        update_charts(self, -1)

    @property
    def reward(self):
        # Minted by the chain itself rather than user activity: coinbase is
        # the PoW reward, coinstake the PoS one. The sync never stores the
        # empty coinbase of a PoS block, so these two flags cover every
        # reward and nothing else.
        return self.coinbase or self.coinstake

    def display(self):
        latest_blocks = Block.select().order_by(orm.desc(Block.height)).first()

        output_amount = 0
        input_amount = 0
        outputs = []
        inputs = []

        for vin in self.inputs:
            inputs.append(
                {
                    "address": vin.vout.address.address,
                    "amount": float(vin.vout.amount),
                }
            )

            input_amount += vin.vout.amount

        for vout in self.outputs:
            outputs.append(
                {
                    "vin": vout.vin.transaction.txid if vout.vin else None,
                    "address": vout.address.address,
                    "amount": float(vout.amount),
                    "category": vout.category,
                    "spent": vout.spent,
                }
            )

            output_amount += vout.amount

        confirmations = -1

        if self.block:
            confirmations = latest_blocks.height - self.block.height + 1

        return {
            "confirmations": confirmations,
            "fee": float(input_amount - output_amount),
            "timestamp": int(self.created.timestamp()),
            "amount": float(self.amount),
            "coinstake": self.coinstake,
            "coinbase": self.coinbase,
            "height": self.height,
            "txid": self.txid,
            "size": self.size,
            "outputs": outputs,
            "mempool": False,
            "inputs": inputs,
        }

    @property
    def timestamp(self):
        return int(self.created.timestamp())

    @property
    def fee(self):
        output_amount = 0
        input_amount = 0
        for vin in self.inputs:
            input_amount += vin.vout.amount

        for vout in self.outputs:
            output_amount += vout.amount

        return float(input_amount - output_amount)

    @property
    def vin(self):
        inputs = self.inputs.order_by(-1)
        return inputs

    @property
    def simple_vin(self):
        result = []
        tmp = {}

        for vin in self.vin:
            if vin.vout.address not in tmp:
                tmp[vin.vout.address] = 0

            tmp[vin.vout.address] += vin.vout.amount

        for address in tmp:
            result.append({"address": address, "amount": tmp[address]})

        return result

    @property
    def vout(self):
        outputs = self.outputs.order_by(-1)
        return outputs

    @property
    def simple_vout(self):
        result = []
        tmp = {}

        for vout in self.vout:
            if vout.address not in tmp:
                tmp[vout.address] = 0

            tmp[vout.address] += vout.amount

        for address in tmp:
            result.append({"address": address, "amount": tmp[address]})

        return result


class Address(db.Entity):
    _table_ = "chain_addresses"

    address = orm.Required(str, index=True)
    outputs = orm.Set("Output")

    transactions = orm.Set(
        "Transaction", table="chain_address_transactions", reverse="addresses"
    )

    issued = orm.Set("Token", reverse="issuer")
    token_balances = orm.Set("TokenBalance")
    balance = orm.Optional("Balance")

    received = orm.Set("Transfer", reverse="receiver")
    sent = orm.Set("Transfer", reverse="sender")

    index = orm.Set("Index")

    @property
    def txcount(self):
        return self.index.count()

    @property
    def txs(self):
        transactions = self.transactions.order_by(-1)
        return transactions


class Balance(db.Entity):
    _table_ = "chain_address_balance"

    amount = orm.Required(Decimal, precision=20, scale=8, default=0)
    address = orm.Required("Address")


class Input(db.Entity):
    _table_ = "chain_inputs"

    sequence = orm.Required(int, size=64)
    n = orm.Required(int)

    transaction = orm.Required("Transaction")
    vout = orm.Required("Output")

    def before_delete(self):
        balance = Balance.get(address=self.vout.address)

        balance.amount += self.vout.amount


class Output(db.Entity):
    _table_ = "chain_outputs"

    amount = orm.Required(Decimal, precision=20, scale=8)
    amount_raw = orm.Required(int, size=64)
    address = orm.Required("Address")
    category = orm.Optional(str)
    txid = orm.Required(str)
    raw = orm.Optional(str)
    n = orm.Required(int)

    vin = orm.Optional("Input", cascade_delete=True)
    transaction = orm.Required("Transaction")
    address = orm.Optional("Address")

    @property
    def spent(self):
        return self.vin is not None

    def before_delete(self):
        balance = Balance.get(address=self.address)

        balance.amount -= self.amount

    orm.composite_index(transaction, n)

    # Backs UTXO gathering in wallet send/sendmany: filter by address and
    # walk outputs largest-first as an index range scan (keyset paginated),
    # avoiding a filesort over the whole unspent set.
    orm.composite_index(address, amount_raw)


class ChartTransactions(db.Entity):
    _table_ = "chain_chart_transactions"

    value = orm.Required(int, default=0)
    time = orm.Required(datetime)


class ChartVolume(db.Entity):
    _table_ = "chain_chart_volume"

    # Decimal, not int: this used to truncate through int(), so every transfer
    # below one coin contributed nothing and everything else was rounded down.
    value = orm.Required(Decimal, precision=20, scale=8, default=0)
    time = orm.Required(datetime)


def update_charts(transaction, sign):
    """Apply a transaction to the daily chart counters.

    ``sign`` is 1 when the transaction is indexed and -1 when it is deleted,
    so a block that gets orphaned unwinds exactly what it added. Both
    directions round the day through utils.datetime_round_day so they always
    land on the same row.

    Every transaction counts, block rewards included. That makes the unwind
    above the load-bearing part: an orphaned block always carries a reward,
    so without it the charts drift on every single reorg.
    """

    time = utils.datetime_round_day(transaction.created)

    if not (transactions_interval := ChartTransactions.get(time=time)):
        transactions_interval = ChartTransactions(time=time)

    transactions_interval.value += sign

    if not (volume_interval := ChartVolume.get(time=time)):
        volume_interval = ChartVolume(time=time)

    volume_interval.value += sign * transaction.amount


db.generate_mapping(create_tables=True)
