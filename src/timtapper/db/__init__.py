#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.942837
Revised: 2026/10/11 16:27:22.477421

Local SQLite persistence: ORM schema, Alembic migrations, session handling.
"""

from db.database import Database

__all__ = ["Database"]
