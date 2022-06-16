import logging
import os

import asyncpg
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1
@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
async def init() -> None:
    host = os.environ.get("POSTGRES_HOST")
    db = os.environ.get("LOG_DB")

    # Check if current session is setup_db session in which case the superuser needs to be used
    is_setup_db = os.environ.get("SETUP_DB")
    if is_setup_db:
        user = os.environ.get("POSTGRES_USER")
        password = os.environ.get("POSTGRES_PASSWORD")
    else:
        user = os.environ.get("LOG_DB_USER")
        password = os.environ.get("LOG_DB_PASSWORD")

    try:
        conn = await asyncpg.connect(
            host=host,
            port=5432,
            user=user,
            password=password,
            database=db,
            timeout=6.0,
            command_timeout=8.0,
        )
        await conn.execute("SELECT 1")
    except Exception as e:
        logger.error(e)
        raise e

    else:
        print("SELECT successful")
        await conn.close()
