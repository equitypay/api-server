from server.models import Transaction
from server.models import Input
from server.models import Peer
from pony import orm


@orm.db_session
def clear_mempool():
    transactions = Transaction.select(lambda t: t.block == None).order_by(
        orm.desc(Transaction.created)
    )

    for transaction in transactions:
        for output in transaction.outputs:
            print(f"Deleting mempool output for {transaction.txid}")

            for input in Input.select(lambda i: i.vout == output):
                input.delete()

            output.delete()

        print(f"Deleting mempool transaction {transaction.txid}")
        transaction.delete()


@orm.db_session
def clear_peers():
    peers = Peer.select().order_by(orm.desc(Peer.last))

    known = []

    for peer in peers:
        if peer.address not in known:
            print(f"Added peer {peer.address} to known")
            known.append(peer.address)
            peer.port = 9998

        else:
            print(f"Deleted peer {peer.address}")
            peer.delete()


if __name__ == "__main__":
    # clear_mempool()
    clear_peers()
