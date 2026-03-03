import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession,async_sessionmaker
from sqlalchemy.orm import sessionmaker,declarative_base

load_dotenv()

DB_URL=os.getenv("DATABASE_URL")

engine=create_async_engine(
    DB_URL,
    echo=True,
)

SessionLocal=async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base=declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session