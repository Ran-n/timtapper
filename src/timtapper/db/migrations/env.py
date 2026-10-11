#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.734582
Revised: 2026/10/11 16:27:22.189070

Alembic environment: runs online against the app's own engine (see Database.migrate).
"""

from alembic import context
from sqlalchemy import create_engine

from db.models import Base

config = context.config
engine = config.attributes.get("connection_engine")
if engine is None:  # `alembic revision --autogenerate` from the CLI during development
    engine = create_engine(config.get_main_option("sqlalchemy.url") or "sqlite:///dev.db")

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
