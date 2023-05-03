from server.models import Transaction
from server.models import Input
from pony import orm

@orm.db_session
def clear_mempool():
    transactions = Transaction.select(
        lambda t: t.block == None
    ).order_by(orm.desc(Transaction.created))

    for transaction in transactions:
        for output in transaction.outputs:
            print(f"Deleting mempool output for {transaction.txid}")

            for input in Input.select(lambda i: i.vout == output):
                input.delete()

            output.delete()

        print(f"Deleting mempool transaction {transaction.txid}")
        transaction.delete()

if __name__ == "__main__":
    clear_mempool()
