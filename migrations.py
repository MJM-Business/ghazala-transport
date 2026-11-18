"""Transactional, versioned migrations for the authoritative SQLite database.

Register future additive schema changes in server.py. Never edit an applied
migration or drop/recreate an existing table to introduce a new version.
The caller owns the transaction, including its startup/bootstrap state.
"""


def apply_migrations(connection, migrations):
    """Apply each registered migration once; a failure rolls back at the caller."""
    if not connection.in_transaction:
        raise RuntimeError("Migrations require an explicit transaction")
    connection.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    registered = sorted(migrations, key=lambda entry: entry[0])
    versions = [entry[0] for entry in registered]
    names = [entry[1] for entry in registered]
    if len(set(versions)) != len(versions) or len(set(names)) != len(names):
        raise RuntimeError("Migration versions and names must be unique")
    applied = {row[0]: row[1] for row in connection.execute(
        "SELECT version, name FROM schema_migrations"
    )}
    if set(applied) - set(versions):
        raise RuntimeError("Database has newer migrations; use its matching server version")
    for version, name, operation in registered:
        if version in applied:
            if applied[version] != name:
                raise RuntimeError("An applied migration was renamed")
            continue
        if applied and version < max(applied):
            raise RuntimeError("New migrations must follow the applied versions")
        operation(connection)
        connection.execute(
            "INSERT INTO schema_migrations(version, name) VALUES(?, ?)",
            (version, name),
        )
        applied[version] = name
