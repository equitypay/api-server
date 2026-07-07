"""One-off migration: add the (address, amount_raw) composite index on
chain_outputs that backs UTXO gathering in wallet send / sendmany.

Why a standalone script when models.py already declares the index?
Pony's generate_mapping(create_tables=True) DOES create a newly-declared
index the first time the updated app boots -- but on a large chain_outputs
table that build runs synchronously and can stall startup. This script lets
you create it deliberately (e.g. during low traffic) up front. It is
idempotent and uses the exact index name Pony derives from
composite_index(address, amount_raw), so the later app boot sees the index
already present and skips it.

    python migrate_output_index.py

Note: the existence check uses MySQL's information_schema (the db config uses
the MySQL param set). On another provider, adjust the check accordingly.
"""

import config
from pony import orm

# Must match the name Pony derives from composite_index(address, amount_raw)
# so app startup treats the index as already created and does not retry it.
INDEX_NAME = "idx_chain_outputs__address_amount_raw"
TABLE = "chain_outputs"
COLUMNS = "address, amount_raw"

# Bind a fresh Database from the same config as the app, but WITHOUT importing
# server.models -- that import calls generate_mapping(create_tables=True) at
# module load, which would create the index as a side effect and defeat the
# point of running this on our own schedule.
db = orm.Database(**config.db)


@orm.db_session
def migrate():
    # MySQL has no CREATE INDEX IF NOT EXISTS, so check first for idempotency.
    exists = db.execute(
        "SELECT 1 FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() "
        "AND table_name = $TABLE AND index_name = $INDEX_NAME LIMIT 1"
    ).fetchone()

    if exists:
        print(f"Index {INDEX_NAME} already exists on {TABLE}, nothing to do.")
        return

    print(f"Creating index {INDEX_NAME} on {TABLE} ({COLUMNS}) ...")
    db.execute(f"CREATE INDEX {INDEX_NAME} ON {TABLE} ({COLUMNS})")
    print("Done.")


if __name__ == "__main__":
    migrate()
