from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from .config import settings

# Railway provides a standard PostgreSQL URL. SQLAlchemy's async engine needs
# the asyncpg driver name, while local Docker Compose already uses it.
database_url = settings.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with SessionLocal() as session:
        yield session
