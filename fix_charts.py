"""Repair the daily chart tables from the transactions already indexed.

The chart counters used to be increment-only: a reorg deleted the orphaned
transactions but left their contribution behind, and the replacement chain
then counted the same transactions again. Whatever is in the two chart tables
today has that drift baked in and cannot be corrected in place, so this
rebuilds both from chain_transactions, which is the source of truth.

It also widens chain_chart_volume.value to numeric(20,8). It used to be an
integer written through int(), which truncated every transfer below one coin
to nothing.

    python fix_charts.py            # asks before writing
    python fix_charts.py --yes      # for non-interactive runs

Run order matters -- the sync must not be writing while this runs, and the
new code expects the widened column:

    1. stop sync.py
    2. deploy the new code
    3. python fix_charts.py
    4. start sync.py

Safe to re-run: it rebuilds the tables from scratch every time.

This talks to PostgreSQL directly rather than going through the ORM. Importing
server.models would run generate_mapping() against the old column type before
the ALTER had a chance to happen, and the aggregation below is a single pass
in the database instead of hydrating every transaction into Python.
"""

from pony import orm
import config
import sys

TRANSACTIONS_TABLE = "chain_chart_transactions"
VOLUME_TABLE = "chain_chart_volume"
SOURCE_TABLE = "chain_transactions"

# Mirrors utils.datetime_round_day (midnight truncation) in the application
# code. Every transaction counts, block rewards included, matching
# update_charts().
DAY = "date_trunc('day', created)"

db = orm.Database(**config.db)


def rebuild(cursor):
    print(f"Widening {VOLUME_TABLE}.value to numeric(20,8) ...")
    cursor.execute(
        f"ALTER TABLE {VOLUME_TABLE} ALTER COLUMN value TYPE numeric(20, 8)"
    )

    print(f"Clearing {TRANSACTIONS_TABLE} and {VOLUME_TABLE} ...")
    cursor.execute(f"DELETE FROM {TRANSACTIONS_TABLE}")
    cursor.execute(f"DELETE FROM {VOLUME_TABLE}")

    print(f"Recounting transactions per day from {SOURCE_TABLE} ...")
    cursor.execute(
        f'INSERT INTO {TRANSACTIONS_TABLE} ("time", value) '
        f"SELECT {DAY} AS day, count(*) "
        f"FROM {SOURCE_TABLE} GROUP BY day"
    )

    print(f"Resumming volume per day from {SOURCE_TABLE} ...")
    cursor.execute(
        f'INSERT INTO {VOLUME_TABLE} ("time", value) '
        f"SELECT {DAY} AS day, sum(amount) "
        f"FROM {SOURCE_TABLE} GROUP BY day"
    )


def summary(cursor):
    cursor.execute(
        f'SELECT count(*), min("time"), max("time"), coalesce(sum(value), 0) '
        f"FROM {TRANSACTIONS_TABLE}"
    )
    days, first, last, transactions = cursor.fetchone()

    cursor.execute(f"SELECT coalesce(sum(value), 0) FROM {VOLUME_TABLE}")
    volume = cursor.fetchone()[0]

    if not days:
        print("\nNo transactions found -- both tables are empty.")
        return

    print(f"\nRebuilt {days} day(s), {first.date()} .. {last.date()}")
    print(f"Transactions: {transactions}")
    print(f"Volume:       {volume}")
    print(
        "\nCross-check a few of these days against "
        "`python daily_transactions.py <start> <finish>` -- the chart counts "
        "every transaction, so it should match Transfers + Rewards."
    )


def main():
    if db.provider.dialect != "PostgreSQL":
        print(
            f"This script is PostgreSQL only (found {db.provider.dialect}); "
            "date_trunc and the ALTER syntax below are not portable."
        )
        return

    print(
        f"This DELETES every row in {TRANSACTIONS_TABLE} and {VOLUME_TABLE} "
        f"and rebuilds them from {SOURCE_TABLE}."
    )
    print("Both tables are derived data -- nothing else references them.")
    print("The sync must be stopped before continuing.")

    if "--yes" not in sys.argv[1:]:
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return

    pool = db.provider.pool
    connection = pool.dbapi_module.connect(*pool.args, **pool.kwargs)

    try:
        cursor = connection.cursor()

        # One transaction: the ALTER, the clear and both rebuilds either all
        # land or none do, so a failure can never leave the charts half built.
        rebuild(cursor)
        connection.commit()

        summary(cursor)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
