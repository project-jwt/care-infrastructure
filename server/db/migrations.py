# db/migrations.py — hand-rolled, idempotent schema migrations run at startup.
#
# There's no Alembic yet. create_all (in main.py's lifespan) only CREATEs
# missing tables — it never ALTERs an existing one — so schema changes to a
# table that's already in a deployed database live here and run once per boot,
# inside the same create_all transaction.
#
# Rules for anything added here:
#   - IDEMPOTENT: safe to run on every restart (guard on current state).
#   - Postgres-only: SQLite is the test DB, where create_all already builds the
#     current schema, so each migration early-returns on other dialects.
# This is a stopgap; once there's more than one, switch to Alembic.

from sqlalchemy import Connection, text


async def run_startup_migrations(async_conn) -> None:
    """Apply migrations create_all can't. Runs on a sync Connection (via
    run_sync) so dialect detection and DDL use the stable sync API."""
    await async_conn.run_sync(_migrate)


def _migrate(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":
        return  # SQLite (local/CI tests): create_all already made the right schema
    _summary_recipients_contact_id_set_null(conn)


def _summary_recipients_contact_id_set_null(conn: Connection) -> None:
    """summary_recipients.contact_id: ON DELETE CASCADE -> SET NULL (and drop
    NOT NULL), so a delivery receipt SURVIVES the recipient deleting their
    account (contact_id becomes NULL = "sent to a deleted user") instead of
    being cascaded away.

    Guarded on the FK's current delete rule, so it runs exactly once:
    confdeltype 'c' = cascade (old — migrate); 'n' = set null (done — skip);
    no row = a fresh DB where create_all already built it as SET NULL (skip).
    """
    rule = conn.execute(
        text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conname = 'summary_recipients_contact_id_fkey'"
        )
    ).scalar()
    # confdeltype is Postgres's internal "char" type; asyncpg hands it back as
    # bytes (b'c'), psql shows it as text ('c') — normalize before comparing.
    if isinstance(rule, (bytes, bytearray)):
        rule = rule.decode()
    if rule != "c":
        return

    conn.execute(text("ALTER TABLE summary_recipients ALTER COLUMN contact_id DROP NOT NULL"))
    conn.execute(text("ALTER TABLE summary_recipients DROP CONSTRAINT summary_recipients_contact_id_fkey"))
    conn.execute(
        text(
            "ALTER TABLE summary_recipients "
            "ADD CONSTRAINT summary_recipients_contact_id_fkey "
            "FOREIGN KEY (contact_id) REFERENCES users(user_id) ON DELETE SET NULL"
        )
    )
