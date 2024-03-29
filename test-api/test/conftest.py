import os
from typing import AsyncGenerator

import asyncpg
import pytest_asyncio
import asyncio
from httpx import AsyncClient
from main import fastapi


# We need to create our own event loop for async testing.
@pytest_asyncio.fixture(scope="session")
def event_loop() -> AsyncGenerator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator:
    async with AsyncClient(app=fastapi, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def db_con() -> AsyncGenerator:
    host = os.environ.get("LOG_DB_HOST")
    port = os.environ.get("LOG_DB_PORT", 5432)
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    database = os.environ.get("POSTGRES_DB")
    acc_table_name = os.environ.get("ACCESS_LOG_TABLE", 'access_logs')
    app_table_name = os.environ.get("APPLICATION_LOG_TABLE", 'application_logs')

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
        await con.execute(f"TRUNCATE TABLE {acc_table_name};")
        await con.execute(f"TRUNCATE TABLE {app_table_name};")
        yield con
        await con.execute(f"TRUNCATE TABLE {acc_table_name};")
        await con.execute(f"TRUNCATE TABLE {app_table_name};")
    except Exception as e:
        print("Something went wrong when connecting to DB")
        raise e
    finally:
        await con.close()
