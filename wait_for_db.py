import logging
import asyncio
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
    user = os.environ.get("LOG_DB_USER")
    password = os.environ.get("LOG_DB_PASSWORD")
    db = "postgres"
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
        await conn.close()


async def main() -> None:
    logger.info("Initializing log collecting service")
    await init()
    logger.info("Service finished initializing. DB is ready.")


if __name__ == "__main__":
    asyncio.run(main())
