"""One-off migration: add the (address, amount_raw) composite index on
chain_outputs that backs UTXO gathering in wallet send / sendmany.

Why a standalone script when models.py already declares the index?
Pony's generate_mapping(create_tables=True) DOES create a newly-declared
index the first time the updated app boots -- but it does so with a plain
CREATE INDEX, which on PostgreSQL takes an ACCESS EXCLUSIVE lock and blocks
writes to chain_outputs for the whole build (i.e. it stalls the syncing
node). This script builds it up front with CREATE INDEX CONCURRENTLY, which
does not block reads or writes, so you can run it on a live node.

    python migrate_output_index.py

It is idempotent (IF NOT EXISTS) and uses the exact index name Pony derives
from composite_index(address, amount_raw), so the later app boot sees the
index already present and skips it.

CONCURRENTLY cannot run inside a transaction block, so this bypasses Pony's
db_session and runs on a dedicated autocommit psycopg2 connection -- reusing
the connection parameters Pony itself resolved from config, so there is no
second place to keep DB credentials in sync.
"""

import config
from pony import orm

# Must match the name Pony derives from composite_index(address, amount_raw)
# so app startup treats the index as already created and does not retry it.
INDEX_NAME = "idx_chain_outputs__address_amount_raw"
TABLE = "chain_outputs"
COLUMNS = "address, amount_raw"

# Bind the Database exactly like the app so Pony resolves the provider and
# connection parameters. We do NOT import server.models -- that import runs
# generate_mapping(create_tables=True) at load time, which would create the
# index (non-concurrently) as a side effect and defeat the point of this
# script.
db = orm.Database(**config.db)


def migrate():
    pool = db.provider.pool

    # Own connection, in autocommit mode: CREATE INDEX CONCURRENTLY is not
    # allowed inside a transaction block.
    connection = pool.dbapi_module.connect(*pool.args, **pool.kwargs)
    connection.autocommit = True

    try:
        cursor = connection.cursor()
        print(f"Creating index {INDEX_NAME} on {TABLE} ({COLUMNS}) ...")
        print("(CONCURRENTLY -- non-blocking, but may take a while.)")
        cursor.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            f"ON {TABLE} ({COLUMNS})"
        )
        print("Done.")
    finally:
        connection.close()


if __name__ == "__main__":
    migrate()
