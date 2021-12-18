from datetime import datetime
from decimal import Decimal
from pony import orm
import config

db = orm.Database(**config.db)

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
    nonce = orm.Required(int)
    size = orm.Required(int)
    bits = orm.Required(str)

    previous_block = orm.Optional("Block")
    transactions = orm.Set("Transaction")
    next_block = orm.Optional("Block")

    @property
    def confirmations(self):
        latest_blocks = Block.select().order_by(
            orm.desc(Block.height)
        ).first()

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
    created = orm.Required(datetime)
    locktime = orm.Required(int)
    size = orm.Required(int)

    block = orm.Required("Block")
    outputs = orm.Set("Output")
    inputs = orm.Set("Input")

    addresses = orm.Set("Address")

    def display(self):
        latest_blocks = Block.select().order_by(
            orm.desc(Block.height)
        ).first()

        output_amount = 0
        input_amount = 0
        outputs = []
        inputs = []

        for vin in self.inputs:
            inputs.append({
                "address": vin.vout.address.address,
                "amount": float(vin.vout.amount)
            })

            input_amount += vin.vout.amount

        for vout in self.outputs:
            outputs.append({
                "vin": vout.vin.transaction.txid if vout.vin else None,
                "address": vout.address.address,
                "amount": float(vout.amount),
                "category": vout.category,
                "spent": vout.spent
            })

            output_amount += vout.amount

        return {
            "confirmations": latest_blocks.height - self.block.height + 1,
            "fee": float(input_amount - output_amount),
            "timestamp": int(self.created.timestamp()),
            "amount": float(self.amount),
            "coinstake": self.coinstake,
            "height": self.block.height,
            "coinbase": self.coinbase,
            "txid": self.txid,
            "size": self.size,
            "outputs": outputs,
            "mempool": False,
            "inputs": inputs
        }

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
            result.append({
                "address": address,
                "amount": tmp[address]
            })

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
            result.append({
                "address": address,
                "amount": tmp[address]
            })

        return result

class Address(db.Entity):
    _table_ = "chain_addresses"

    address = orm.Required(str, index=True)
    outputs = orm.Set("Output")

    transactions = orm.Set(
        "Transaction", table="chain_address_transactions",
        reverse="addresses"
    )

    balance = orm.Optional("Balance")

    @property
    def txcount(self):
        return self.transactions.count()

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
        balance = Balance.get(
            address=self.vout.address
        )

        balance.amount += self.vout.amount

class Output(db.Entity):
    _table_ = "chain_outputs"

    amount = orm.Required(Decimal, precision=20, scale=8)
    address = orm.Required("Address")
    category = orm.Optional(str)
    raw = orm.Optional(str)
    n = orm.Required(int)

    vin = orm.Optional("Input", cascade_delete=True)
    transaction = orm.Required("Transaction")
    address = orm.Optional("Address")

    @property
    def spent(self):
        return self.vin is not None

    def before_delete(self):
        balance = Balance.get(
            address=self.address
        )

        balance.amount -= self.amount

    orm.composite_index(transaction, n)


db.generate_mapping(create_tables=True)