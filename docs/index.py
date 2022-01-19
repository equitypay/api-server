from server.services import IndexService
from server.models import Transaction
from pony import orm

with orm.db_session:
    transactions = Transaction.select()

    for transaction in transactions:
        print(f"Processing transaction {transaction.txid} (block {transaction.block.height})")

        for address in transaction.addresses:
            IndexService.create(address, transaction)

        for transfer in transaction.transfers:
            IndexService.create(transfer.receiver, transaction)
            IndexService.create(transfer.sender, transaction)

        orm.commit()
