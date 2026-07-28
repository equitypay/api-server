"""Per-day chain activity: blocks, transfers and block rewards.

Transactions are split into three buckets:

    transfers -- regular user activity
    pow       -- coinbase, the reward of a proof-of-work block
    pos       -- coinstake, the reward of a proof-of-stake block

The sync never stores the empty coinbase of a PoS block at all, so the
coinbase/coinstake flags cover every reward and nothing else.

    python daily_transactions.py                    # 18-07-2026 .. 24-07-2026
    python daily_transactions.py 01-07-2026 07-07-2026

Dates are DD-MM-YYYY and both ends are inclusive. Days with no activity are
printed as 0 rather than skipped.

Block.created and Transaction.created are both written by the sync as
datetime.fromtimestamp(), i.e. naive local time of the syncing machine, so
the day boundaries here are that same local time.
"""

from datetime import datetime, timedelta
from server.models import Transaction
from server.models import Block
from pony import orm
import sys

DEFAULT_FINISH = "24-07-2026"
DEFAULT_START = "18-07-2026"
DATE_FORMAT = "%d-%m-%Y"


def format_row(label, blocks, transfers, rewards, pow_count, pos_count):
    return (
        f"{label:<12}"
        f"{blocks:>8}"
        f"{transfers:>11}"
        f"{rewards:>9}"
        f"{pow_count:>7}"
        f"{pos_count:>7}"
    )


@orm.db_session
def daily_stats(start, finish):
    # finish is inclusive, so scan up to the start of the following day.
    limit = finish + timedelta(days=1)

    stats = {}
    day = start

    while day < limit:
        stats[day.date()] = {
            "blocks": 0,
            "transfers": 0,
            "pow": 0,
            "pos": 0,
        }
        day += timedelta(days=1)

    # The id is selected only to keep the rows unique: Pony adds DISTINCT to
    # queries that return plain attributes, which would collapse two rows
    # sharing a timestamp into one and undercount the day.
    blocks = orm.select(
        (b.id, b.created)
        for b in Block
        if b.created >= start and b.created < limit
    )

    for _, timestamp in blocks:
        stats[timestamp.date()]["blocks"] += 1

    transactions = orm.select(
        (t.id, t.created, t.coinbase, t.coinstake)
        for t in Transaction
        if t.created >= start and t.created < limit
    )

    for _, timestamp, coinbase, coinstake in transactions:
        entry = stats[timestamp.date()]

        if coinbase:
            entry["pow"] += 1
        elif coinstake:
            entry["pos"] += 1
        else:
            entry["transfers"] += 1

    return stats


def main():
    args = sys.argv[1:]

    raw_start = args[0] if len(args) > 0 else DEFAULT_START
    raw_finish = args[1] if len(args) > 1 else DEFAULT_FINISH

    try:
        start = datetime.strptime(raw_start, DATE_FORMAT)
        finish = datetime.strptime(raw_finish, DATE_FORMAT)
    except ValueError:
        print(f"Dates must be in {DATE_FORMAT} format, e.g. {DEFAULT_START}")
        return

    if finish < start:
        print("Finish date must not be earlier than start date")
        return

    stats = daily_stats(start, finish)

    totals = {"blocks": 0, "transfers": 0, "pow": 0, "pos": 0}

    print(format_row("Date", "Blocks", "Transfers", "Rewards", "PoW", "PoS"))

    for day in sorted(stats):
        entry = stats[day]

        for key in totals:
            totals[key] += entry[key]

        print(
            format_row(
                day.strftime(DATE_FORMAT),
                entry["blocks"],
                entry["transfers"],
                entry["pow"] + entry["pos"],
                entry["pow"],
                entry["pos"],
            )
        )

    print(
        format_row(
            "Total",
            totals["blocks"],
            totals["transfers"],
            totals["pow"] + totals["pos"],
            totals["pow"],
            totals["pos"],
        )
    )


if __name__ == "__main__":
    main()
