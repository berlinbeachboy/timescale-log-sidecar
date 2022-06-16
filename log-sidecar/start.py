from wait_for_db import init
from setup_db import setup_db
from main import main
import os
import asyncio


async def pre_start():
    print("here")
    await init() # wait for db
    setup = os.environ.get("SETUP_DB", "0")
    print(setup)
    if os.environ.get("SETUP_DB") == "1":
        print("SETUP_DB env variable is set. Setting up DB.")
        await setup_db()


async def start():
    await pre_start()
    await main()

if __name__ == "__main__":
    asyncio.run(start())


