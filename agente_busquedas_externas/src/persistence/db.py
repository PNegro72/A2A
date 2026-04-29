import os
from pathlib import Path

import aiosqlite

_SCHEMA = (Path(__file__).parent / "schema_sqlite.sql").read_text()


async def get_connection() -> aiosqlite.Connection:
    db_path = os.getenv("DB_PATH", "./agente_busquedas_externas.db")
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(_SCHEMA)
    await conn.commit()
    return conn
