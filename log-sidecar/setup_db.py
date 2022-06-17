import asyncpg
from asyncpg import Connection
import os


async def create_access_log_table(con: Connection, table_name: str) -> bool:
    stmt = f"""CREATE TABLE IF NOT EXISTS {table_name} (
    time                   TIMESTAMP         NOT NULL,
    application_name       VARCHAR(20)       NOT NULL,
    environment_name       VARCHAR(10)       NOT NULL,
    trace_id               VARCHAR(36)       NOT NULL,
    host_ip                VARCHAR(39)       NOT NULL,
    remote_ip_address      VARCHAR(39)       NOT NULL,
    username               VARCHAR(50)       NOT NULL,
    request_method         VARCHAR(7)        NOT NULL,
    request_path           TEXT              NOT NULL,
    response_status        SMALLINT          NOT NULL,
    duration               NUMERIC(9,3)      NOT NULL,
    response_size          INTEGER           NOT NULL,
    data                   JSONB             NULL,
    PRIMARY KEY(time, trace_id)
    );"""
    result = await con.execute(stmt)
    print(result)
    return True


async def create_application_log_table(con: Connection, table_name: str) -> bool:
    stmt = f"""CREATE TABLE IF NOT EXISTS {table_name} (
    time                   TIMESTAMP         NOT NULL,
    application_name       VARCHAR(20)       NOT NULL,
    environment_name       VARCHAR(10)       NOT NULL,
    trace_id               VARCHAR(36)       NOT NULL,
    host_ip                VARCHAR(39)       NOT NULL,
    username               VARCHAR(50)       NOT NULL,
    level                  VARCHAR(10)       NOT NULL,
    file_path              TEXT              NOT NULL,
    message                TEXT              NOT NULL,
    data                   JSONB             NULL,
    PRIMARY KEY(time, trace_id)
    );"""
    result = await con.execute(stmt)
    print(result)
    return True


async def create_access_table_indices(con: Connection, table_name: str) -> bool:
    stmt = f"""CREATE INDEX ON {table_name} (request_path, trace_id, time DESC) 
              WHERE request_path IS NOT NULL AND trace_id IS NOT NULL;"""
    result = await con.execute(stmt)
    print(result)
    return True


async def create_application_table_indices(con: Connection, table_name: str) -> bool:
    stmt = f"""CREATE INDEX ON {table_name} (level, trace_id, time DESC) 
              WHERE level IS NOT NULL AND trace_id IS NOT NULL;"""
    result = await con.execute(stmt)
    print(result)
    return True


async def create_hypertables(con: Connection, table_name: str, partitioning_interval: str) -> bool:
    stmt = f"SELECT create_hypertable('{table_name}', 'time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '{partitioning_interval}')"
    result = await con.execute(stmt)
    print(result)
    return True


async def create_user(con: Connection, user: str, password: str) -> bool:
    stmt = f"""  
              DO
              $do$
              BEGIN
                IF EXISTS (
                    SELECT FROM pg_catalog.pg_roles
                    WHERE  rolname = '{user}') THEN
                    RAISE NOTICE 'Role {user} already exists. Skipping.';
                 ELSE
                    CREATE ROLE {user} with LOGIN ENCRYPTED PASSWORD '{password}';
                 END IF;
              END
              $do$;
            """
    result = await con.execute(stmt)
    print(result)
    return True


async def give_user_permission(con: Connection, table_name: str, user: str) -> bool:
    stmt = f"""GRANT INSERT, UPDATE, SELECT ON TABLE {table_name} TO {user};"""
    result = await con.execute(stmt)
    print(result)
    return True


async def setup_db() -> None:
    """ When setting up DB the POSTGRES_DB variable is used to indicate the database name.
    This is because it is a fixed env variable for the postgres/timescale container.
    When running, use the LOG_DB variable, so that the actual application can have its own postgres"""

    host = os.environ.get("POSTGRES_HOST")
    port = os.environ.get("POSTGRES_PORT", 5432)
    superuser = os.environ.get("POSTGRES_USER")
    su_password = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")

    log_db_user = os.environ.get("LOG_DB_USER")
    log_db_password = os.environ.get("LOG_DB_PASSWORD")

    access_log_table = os.environ.get("ACCESS_LOG_TABLE")
    application_log_table = os.environ.get("APPLICATION_LOG_TABLE")

    partitioning_interval = os.environ.get("PARTITIONING_INTERVAL")

    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=superuser,
            password=su_password,
            database=db,
            timeout=6.0,
            command_timeout=8.0,
        )

    except Exception as e:
        raise e

    await create_access_log_table(conn, access_log_table)
    await create_application_log_table(conn, application_log_table)

    await create_access_table_indices(conn, access_log_table)
    await create_application_table_indices(conn, application_log_table)

    await create_hypertables(conn, access_log_table, partitioning_interval)
    await create_hypertables(conn, application_log_table, partitioning_interval)

    await create_user(conn, log_db_user, log_db_password)
    await give_user_permission(conn, access_log_table, log_db_user)
    await give_user_permission(conn, application_log_table, log_db_user)

    await conn.close()





