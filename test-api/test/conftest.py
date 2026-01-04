import os
from asyncio import AbstractEventLoop
from typing import AsyncGenerator, Generator

import asyncpg
import pytest_asyncio
import asyncio

from asyncpg import Connection
from httpx import AsyncClient, ASGITransport
from main import fastapi


# We need to create our own event loop for async testing.
@pytest_asyncio.fixture(scope="session")
def event_loop() -> Generator[AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=fastapi), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def db_con() -> AsyncGenerator[Connection, None]:
    host = os.environ.get("LOG_DB_HOST")
    port = os.environ.get("LOG_DB_PORT", 5432)
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    database = os.environ.get("POSTGRES_DB")

    con = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        timeout=6.0,
        command_timeout=8.0,
    )
    try:
        yield con
    except Exception as e:
        print("Something went wrong when connecting to DB")
        raise e
    finally:
        await con.close()
