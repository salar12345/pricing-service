import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://pricing:pricing@localhost:5432/pricing")
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="pricing",
    )

    with context.begin_transaction():
        context.execute(text("CREATE SCHEMA IF NOT EXISTS pricing"))
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS pricing"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="pricing",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
