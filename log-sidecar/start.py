import os
import asyncio
import logging

from wait_for_db import init
from setup_db import setup_db
from main import main

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def pre_start():
    await init()  # wait for db
    if os.environ.get("SETUP_DB", "0") == "1":
        logger.info("SETUP_DB env variable is set. Setting up DB.")
        await setup_db()


async def start():
    await pre_start()
    await main()


if __name__ == "__main__":
    asyncio.run(start())
