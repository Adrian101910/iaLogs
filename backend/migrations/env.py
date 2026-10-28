import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.models import Base

config = context.config
target_metadata = Base.metadata
url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
