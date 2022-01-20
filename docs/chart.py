from server.services import ChartTransactionsService
from server.services import ChartVolumeService
from server.models import Transaction
from server import utils
from pony import orm

with orm.db_session:
    for transaction in Transaction.select():
        print(f"Processing transaction {transaction.txid} (block {transaction.block.height})")

        time = utils.datetime_round_day(transaction.created)

        transactions_interval = ChartTransactionsService.get_by_time(time)
        if not transactions_interval:
            transactions_interval = ChartTransactionsService.create(time)

        transactions_interval.value += 1

        volume_interval = ChartVolumeService.get_by_time(time)
        if not volume_interval:
            volume_interval = ChartVolumeService.create(time)

        volume_interval.value += int(transaction.amount)

        orm.commit()
