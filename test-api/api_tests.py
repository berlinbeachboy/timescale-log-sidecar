import asyncio
import os
from httpx import AsyncClient
from asyncpg import Connection

import pytest

pytestmark = pytest.mark.asyncio

@pytestmark
async def test_hello_endpoint(
    client: AsyncClient, db_con: Connection
) -> None:
    """ WARNING: AFTER RUNNING TESTS THE DB WILL BE TRUNCATED!!! """
    r = await client.get(
        f"/log_hello",
    )
    assert 200 <= r.status_code < 300

    await asyncio.sleep(6)
    acc_table_name = os.environ.get("ACCESS_LOG_TABLE", 'access_logs')
    app_table_name = os.environ.get("APPLICATION_LOG_TABLE", 'application_logs')
    access_count = await db_con.fetchval(f"SELECT count(*) FROM {acc_table_name};")
    application_count = await db_con.fetchval(f"SELECT count(*) FROM {app_table_name};")

    assert access_count == application_count == 1

    r = await client.get(
        f"/log_error",
    )
    assert 400 <= r.status_code < 500

    await asyncio.sleep(6)
    access_count = await db_con.fetchval(f"SELECT count(*) FROM {acc_table_name};")
    application_count = await db_con.fetchval(f"SELECT count(*) FROM {app_table_name};")
    assert access_count == application_count == 2
    error_count = await db_con.fetchval(f"SELECT count(*) FROM {app_table_name} WHERE level = 'ERROR';")
    assert error_count == 1