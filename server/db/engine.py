# TODO: build an async engine from settings.database_url and expose AsyncSessionLocal
# for dependencies/db.py to yield per request. DATABASE_URL uses the
# postgresql+asyncpg:// scheme.

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# engine = create_async_engine(...)
# AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
