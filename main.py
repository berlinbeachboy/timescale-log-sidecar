import errno
import os
import json
import random
import asyncio
import logging
from typing import List

import asyncpg
import datetime

log_level = os.environ.get("SIDECAR_LOG_LEVEL") if "SIDECAR_LOG_LEVEL" in os.environ else logging.WARN
logging.basicConfig(level=log_level)
logger = logging.getLogger("sidecar")

FIFO_PATH = os.environ.get("NAMED_PIPE_FOLDER") + "/" + os.environ.get("NAMED_PIPE_FILE")
SENDING_INTERVAL = int(os.environ.get("SENDING_INTERVAL")) if "SENDING_INTERVAL" in os.environ else 5
logger.debug(f"LOG LEVEL set to debug")
logger.debug(f"FIFO PATH: {FIFO_PATH}")
logger.debug(f"SENDING INTERVALL : {str(SENDING_INTERVAL)}")

class Buffer:
    """ The Buffer with a lock that contains the read lines.
    """
    def __init__(self, interval=5):
        self.interval = interval
        self.lock = asyncio.Semaphore(value=1)
        self.buf = []

    def send_logs_every(self):
        jitter = random.randint(1, 9) * 0.1
        return self.interval + jitter


def prep_access_log(log: dict):
    if not "time" in log or not log["time"]:
        time = datetime.datetime.utcnow()
    else:
        time = datetime.datetime.strptime(log["time"], "%Y-%m-%d %H:%M:%S.%f")
    application_name = log["application_name"] if "application_name" in log and log["application_name"] else "unknown"
    environment_name = log["environment_name"] if "environment_name" in log and log["environment_name"] else "unknown"
    trace_id = log["trace_id"] if "trace_id" in log and log["trace_id"] else "unknown"
    host_ip = log["host_ip"] if "host_ip" in log and log["host_ip"] else "unknown"
    remote_ip_address = log["remote_ip_address"] if "remote_ip_address" in log and log["remote_ip_address"] else "unknown"
    username = log["username"] if "username" in log and log["username"] else "unknown"
    request_method = log["request_method"] if "request_method" in log and log["request_method"] else "unknown"
    request_path = log["request_path"] if "request_path" in log and log["request_path"] else "unknown"
    response_status = log["response_status"] if "response_status" in log and log["response_status"] else "unknown"
    duration = log["duration"] if "duration" in log and log["duration"] else 0
    data = log.get("data")
    if data:
        data = json.dumps(data)
    return (time,
            application_name,
            environment_name,
            trace_id,
            host_ip,
            remote_ip_address,
            username,
            request_method,
            request_path,
            response_status,
            duration,
            data
            )

def prep_application_log(log: dict):
    if not "time" in log or not log["time"]:
        time = datetime.datetime.utcnow()
    else:
        time = datetime.datetime.strptime(log["time"], "%Y-%m-%d %H:%M:%S.%f")
    application_name = log["application_name"] if "application_name" in log and log["application_name"] else "unknown"
    environment_name = log["environment_name"] if "environment_name" in log and log["environment_name"] else "unknown"
    trace_id = log["trace_id"] if "trace_id" in log and log["trace_id"] else "unknown"
    host_ip = log["host_ip"] if "host_ip" in log and log["host_ip"] else "unknown"
    level = log["level"] if "level" in log and log["level"] else "unknown"
    file_path = log["file_path"] if "file_path" in log and log["file_path"] else "unknown"
    username = log["username"] if "username" in log and log["username"] else "unknown"
    message = log["message"] if "message" in log and log["message"] else ""
    data = log.get("data")
    if data:
        data = json.dumps(data)
    return (time,
            application_name,
            environment_name,
            trace_id,
            host_ip,
            username,
            level,
            file_path,
            message,
            data
            )

async def send_access_logs(con, access_logs):
    table_name = os.environ.get("ACCESS_LOG_TABLE")
    await con.executemany(
        f"""
        INSERT INTO {table_name}(time, application_name, environment_name, trace_id, host_ip, remote_ip_address, username, request_method, 
        request_path, response_status, duration, data)
                  VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
        access_logs,
        timeout=8.0,
    )

async def send_application_logs(con, app_logs):
    table_name = os.environ.get("APPLICATION_LOG_TABLE")
    await con.executemany(
        f"""
        INSERT INTO {table_name}(time, application_name, environment_name, trace_id, host_ip, username, level, 
        file_path, message, data)
                  VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        app_logs,
        timeout=8.0,
    )


async def send_logs_to_db(logs: List[dict]):
    host = os.environ.get("POSTGRES_HOST")
    user = os.environ.get("LOG_DB_USER")
    password = os.environ.get("LOG_DB_PASSWORD")
    database = os.environ.get("LOG_DB")
    try:
        con = await asyncpg.connect(
            host=host,
            port=5432,
            user=user,
            password=password,
            database=database,
            timeout=6.0,
            command_timeout=8.0,
        )

        access_logs = []
        application_logs = []
        for i in logs:
            if not "type" in i:
                continue
            if i["type"].lower() == "access":
                prepped_log = prep_access_log(log=i)
                logger.debug(prepped_log)
                access_logs.append(prepped_log)
            elif i["type"].lower() == "application":
                prepped_log = prep_application_log(log=i)
                logger.debug(prepped_log)
                application_logs.append(prepped_log)
            else:
                logger.info("Cannot send logs other than type access or application")
        await send_access_logs(con, access_logs)
        await send_application_logs(con, application_logs)
        logger.debug(f"sent {len(logs)} logs")
        await con.close()
    except Exception as e:
        logger.error(e)


async def schedule_log_sending(buffered_logs):
    while True:
        async with buffered_logs.lock:
            if len(buffered_logs.buf) > 0:
                await send_logs_to_db(logs=buffered_logs.buf)
                buffered_logs.buf = []
        await asyncio.sleep(buffered_logs.send_logs_every())


def open_fifo(fifo_file):
    try:
        os.mkfifo(fifo_file, mode=0o777)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e
    return fifo_file


class PIPE:
    """ The Pipe / Context Manager to access the fifo in sync and async manner.
    Use like:
      async with PIPE() as pipe:
        data = pipe.readline()
    """
    fifo_file = None

    def __enter__(self):
        try:
            self.fifo_file = open(FIFO_PATH, mode="r")
        except FileNotFoundError:
            open_fifo(FIFO_PATH)
            self.fifo_file = open(FIFO_PATH, mode="r")
        os.set_blocking(self.fifo_file.fileno(), False)
        return self.fifo_file

    def __exit__(self, type, value, traceback):
        if self.fifo_file:
            self.fifo_file.close()

    async def __aenter__(self):
        try:
            self.fifo_file = open(FIFO_PATH, mode="r")
        except FileNotFoundError:
            open_fifo(FIFO_PATH)
            self.fifo_file = open(FIFO_PATH, mode="r")
        os.set_blocking(self.fifo_file.fileno(), False)
        return await asyncio.sleep(-1, result=self.fifo_file)

    async def __aexit__(self, exc_type, exc, tb):
        if self.fifo_file:
            await asyncio.sleep(-1, result=self.fifo_file.close())


async def collect_logs(buffered_logs):
    async with PIPE() as pipe:
        while True:
            try:
                data = pipe.readline()
                if len(data) == 0:
                    await asyncio.sleep(1)
                    continue
                log = json.loads(data)
                if log:
                    logger.debug("Collected a log")
                    # buffer log events in memory
                    async with buffered_logs.lock:
                        buffered_logs.buf.append(log)
            except OSError as e:
                logger.error(e)


async def main():

    buffered_logs = Buffer(SENDING_INTERVAL)
    return await asyncio.gather(collect_logs(buffered_logs), schedule_log_sending(buffered_logs))


if __name__ == '__main__':
    asyncio.run(main())