import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_async_engine(
    DB_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def init_pgvector() -> None:
    """Register pgvector asyncpg codecs on the engine's connection pool."""
    from pgvector.asyncpg import register_vector

    async with engine.connect() as conn:
        await conn.run_sync(register_vector)


async def get_db():
    async with SessionLocal() as session:
        yield session
