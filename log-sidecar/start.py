import os
import asyncio
import logging
from pathlib import Path

import asyncpg
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from setup_db import setup_db
from main import main

PIPEDIR = Path("/tmp/namedPipes")

log_level = os.environ.get("SIDECAR_LOG_LEVEL", logging.WARN)
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 2


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
async def wait_for_db() -> None:
    host = os.environ.get("LOG_DB_HOST", "db")
    port = os.environ.get("LOG_DB_PORT", 5432)
    db = os.environ.get("LOG_DB_NAME", "logs")

    # Check if current session is setup_db session in which case the superuser needs to be used
    if os.environ.get("SETUP_DB", 0):
        user = os.environ.get("POSTGRES_USER")
        password = os.environ.get("POSTGRES_PASSWORD")
    else:
        user = os.environ.get("LOG_DB_USER")
        password = os.environ.get("LOG_DB_PASSWORD")
    logger.debug(f"Trying to connect with host {host}, user {user}, db {db}")
    conn = None
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db,
            timeout=6.0,
            command_timeout=8.0,
        )
        await conn.execute("SELECT 1")
        logger.info("DB connection initialized.")
    except Exception as e:
        logger.error(e)
        raise e
    finally:
        if conn:
            await conn.close()


async def pre_start():
    await wait_for_db()  # wait for db
    if os.environ.get("SETUP_DB", "0") == "1":
        logger.warning("SETUP_DB env variable is set. Setting up DB.")
        await setup_db()


async def start():
    PIPEDIR.mkdir(parents=True, exist_ok=True)
    await pre_start()
    await main()


if __name__ == "__main__":
    asyncio.run(start())
