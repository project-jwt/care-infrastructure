# TODO: build a psycopg_pool.ConnectionPool from settings.database_url.
# Prefer a single connection string in DATABASE_URL for both local dev and Render.

from psycopg_pool import ConnectionPool

# pool = ConnectionPool(...)
