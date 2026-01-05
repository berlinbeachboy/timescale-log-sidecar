import errno
import os
import json
import time
import random
import asyncio
import logging
from datetime import datetime
from collections import deque
from pathlib import Path

import asyncpg

log_level = os.environ.get("SIDECAR_LOG_LEVEL", logging.WARN)
logging.basicConfig(level=log_level)
logger = logging.getLogger("sidecar")
logger.setLevel(log_level)

FIFO_PATH = os.environ.get("NAMED_PIPE_FOLDER", "/tmp/namedPipes") + "/" + os.environ.get("NAMED_PIPE_FILE", "appLogs")
SENDING_INTERVAL = int(os.environ.get("LOG_SENDING_INTERVAL", 5))
BACKOFF_INITIAL = float(os.environ.get("SIDECAR_BACKOFF_INITIAL", 2.0))   # seconds
BACKOFF_MAX = float(os.environ.get("SIDECAR_BACKOFF_MAX", 60.0))          # seconds
BACKOFF_FACTOR = float(os.environ.get("SIDECAR_BACKOFF_FACTOR", 2.0))     # multiplier
DB_TIMEOUT = 8.0

logger.debug("LOG LEVEL set to debug")
logger.debug(f"FIFO PATH: {FIFO_PATH}")
logger.debug(f"SENDING INTERVAL : {str(SENDING_INTERVAL)}")

host = os.environ.get("LOG_DB_HOST", "timescale_db")
port = os.environ.get("LOG_DB_PORT", 5432)
user = os.environ.get("LOG_DB_USER", "log_api_user")
database = os.environ.get("LOG_DB_NAME", "logs")
password = os.environ.get("LOG_DB_PASSWORD")
if not password:
    raise Exception("No password set for log_api_user. Please set via the LOG_DB_PASSWORD env variable.")


class Buffer:
    """In-memory bounded buffer for logs with async lock."""

    def __init__(self, interval=5, max_size=1000):
        self.interval = interval
        self.lock = asyncio.Lock()
        self.buf = deque(maxlen=max_size)
        self.max_size = max_size
        self.dropped = 0

    async def add(self, log_in: dict):
        async with self.lock:
            # deque(maxlen=N) automatically drops oldest item if full
            if len(self.buf) == self.max_size:
                self.dropped += 1
            self.buf.append(log_in)

    async def remove_left(self, count: int):
        async with self.lock:
            for _ in range(min(count, len(self.buf))):
                self.buf.popleft()

    def send_logs_every(self):
        jitter = random.randint(1, 9) * 0.1
        return self.interval + jitter


def prep_access_log(log: dict) -> tuple | None:
    """This function takes the read log dict and outputs an access_log formatted tuple.
    The tuple is ready for injecting to db with asyncpg"""

    try:
        if "time" not in log or not log["time"]:
            t = datetime.fromtimestamp(time.time(), tz=None)
        else:
            t = datetime.strptime(log["time"], "%Y-%m-%d %H:%M:%S.%f")
        application_name = (
            log["application_name"][:20] if "application_name" in log and log["application_name"] else "unknown"
        )
        environment_name = (
            log["environment_name"][:10] if "environment_name" in log and log["environment_name"] else "unknown"
        )
        trace_id = log["trace_id"] if "trace_id" in log and log["trace_id"] else "unknown"
        host_ip = log["host_ip"] if "host_ip" in log and log["host_ip"] else "unknown"
        remote_ip_address = (
            log["remote_ip_address"] if "remote_ip_address" in log and log["remote_ip_address"] else "unknown"
        )
        username = log["username"][:49] if "username" in log and log["username"] else "unknown"
        request_method = log["request_method"][:7] if "request_method" in log and log["request_method"] else "unknown"
        request_path = log["request_path"] if "request_path" in log and log["request_path"] else "unknown"
        response_status = int(log["response_status"]) if "response_status" in log and log["response_status"] \
            else "unknown"
        response_size = int(log["response_size"]) if "response_size" in log and log["response_size"] else 0
        duration = float(log["duration"]) if "duration" in log and log["duration"] else 0
        data = log.get("data")
        if data:
            try:
                data = json.dumps(data)
            except TypeError as e:
                logger.error(f"Failed to serialize data for access log: {e}")
                data = None

        return (
            t,
            application_name,
            environment_name,
            trace_id,
            host_ip,
            remote_ip_address,
            username,
            request_method,
            request_path,
            response_status,
            response_size,
            duration,
            data,
        )
    except Exception as e:
        logger.error(f"Failed to prep access log: {e}")
        return None


def prep_application_log(log: dict) -> tuple | None:
    """This function takes the read log dict and outputs an application_log formatted tuple.
    The tuple is ready for injecting to db with asyncpg"""
    try:
        if "time" not in log or not log["time"]:
            t = datetime.fromtimestamp(time.time(), tz=None)
        else:
            t = datetime.strptime(log["time"], "%Y-%m-%d %H:%M:%S.%f")
        application_name = (
            log["application_name"][:20] if "application_name" in log and log["application_name"] else "unknown"
        )
        environment_name = (
            log["environment_name"][:10] if "environment_name" in log and log["environment_name"] else "unknown"
        )
        trace_id = log["trace_id"] if "trace_id" in log and log["trace_id"] else "unknown"
        host_ip = log["host_ip"] if "host_ip" in log and log["host_ip"] else "unknown"
        level = log["level"] if "level" in log and log["level"] else "unknown"
        file_path = log["file_path"] if "file_path" in log and log["file_path"] else "unknown"
        username = log["username"][:49] if "username" in log and log["username"] else "unknown"
        message = log["message"] if "message" in log and log["message"] else ""
        data = log.get("data")
        if data:
            try:
                data = json.dumps(data)
            except TypeError as e:
                logger.error(f"Failed to serialize data for application log: {e}")
                data = None
        return t, application_name, environment_name, trace_id, host_ip, username, level, file_path, message, data
    except Exception as e:
        logger.error(f"Failed to prep application log: {e}")
        return None


async def send_access_logs(con, access_logs: list[tuple]):
    table_name = os.environ.get("ACCESS_LOG_TABLE", "access_logs")
    await con.executemany(
        f"""
        INSERT INTO {table_name}(
        time, application_name, environment_name, trace_id, host_ip, remote_ip_address, username, request_method,
         request_path, response_status, response_size, duration, data)
                  VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        access_logs,
        timeout=DB_TIMEOUT,
    )


async def send_application_logs(con, app_logs: list[tuple]):
    table_name = os.environ.get("APPLICATION_LOG_TABLE", "application_logs")
    await con.executemany(
        f"""
        INSERT INTO {table_name}(time, application_name, environment_name, trace_id, host_ip, username, level,
         file_path, message, data)
                  VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        app_logs,
        timeout=DB_TIMEOUT,
    )


async def send_logs_to_db(logs: list[dict]) -> bool:
    access_logs = []
    application_logs = []

    for i in logs:
        if "type" not in i:
            continue
        if i["type"].lower() == "access":
            prepped = prep_access_log(log=i)
            if prepped is not None:
                access_logs.append(prepped)
        elif i["type"].lower() == "application":
            prepped = prep_application_log(log=i)
            if prepped is not None:
                application_logs.append(prepped)
        else:
            logger.info("Cannot send logs other than type access or application")

    if len(access_logs) == 0 and len(application_logs) == 0:
        return True

    con = None
    try:
        con = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            timeout=DB_TIMEOUT,
            command_timeout=DB_TIMEOUT,
        )
        logger.debug(f"Connected with host {host}, user {user}, db {database}")

        if len(access_logs) > 0:
            await send_access_logs(con, access_logs)
            logger.debug(f"sent {len(access_logs)} access_logs")

        if len(application_logs) > 0:
            await send_application_logs(con, application_logs)
            logger.debug(f"sent {len(application_logs)} application_logs")

        return True

    except Exception as e:
        logger.error(f"DB send failed: {e}")
        return False

    finally:
        if con:
            try:
                await con.close()
            except Exception:
                pass


async def schedule_log_sending(buffered_logs: Buffer):
    """Schedules sending logs to db. Uses exponential backoff on DB failures.
    - Success => reset to normal interval
    - Failure => increase delay up to BACKOFF_MAX
    """

    backoff = BACKOFF_INITIAL
    while True:
        to_send = None
        sleep_for = buffered_logs.send_logs_every()

        async with buffered_logs.lock:
            if len(buffered_logs.buf) > 0:
                # snapshot current buffer
                to_send = list(buffered_logs.buf)

        if to_send:
            ok = False
            try:
                ok = await send_logs_to_db(logs=to_send)
            except Exception as e:
                logger.error(f"Unexpected send failure: {e}")

            if ok:
                # remove the logs we sent from ring buffer
                await buffered_logs.remove_left(count=len(to_send))
                backoff = BACKOFF_INITIAL  # reset backoff after success
                logger.debug(f"Sent {len(to_send)} logs. Next send in ~{sleep_for:.1f}s")
            else:
                async with buffered_logs.lock:
                    logger.warning(
                        f"DB unavailable / insert failed. Keeping {len(buffered_logs.buf)} buffered logs "
                        f"(dropped_total={buffered_logs.dropped})"
                    )
                sleep_for = backoff + random.random() * 0.5
                backoff = min(backoff * BACKOFF_FACTOR, BACKOFF_MAX)

        await asyncio.sleep(sleep_for)


def open_fifo(fifo_file):
    try:
        os.mkfifo(fifo_file)
        os.chmod(fifo_file, 0o777)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e
    logger.info(f"Created new pipe: {fifo_file}")
    return fifo_file


class PIPE:
    """The Pipe / Context Manager to access the fifo in sync and async manner.
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

    def __exit__(self, pipe_type, value, traceback):
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


async def collect_logs(buffered_logs: Buffer):
    """Function that keeps running and collects logs from the named pipe"""
    async with PIPE() as pipe:
        while True:
            try:
                data = pipe.readline()
                if len(data) == 0:
                    await asyncio.sleep(1)
                    continue
                try:
                    log = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Cannot decode log: {e}")
                    continue
                if log:
                    logger.debug("Collected a log")
                    await buffered_logs.add(log)
            except Exception as e:
                logger.error(e)


async def main():
    buffered_logs = Buffer(SENDING_INTERVAL)
    try:
        v = Path.open("./.version", mode="r+").readline()
    except Exception:
        v = "unknown Version"
    logger.info(f"Starting Log Sidecar, version {v}")
    return await asyncio.gather(collect_logs(buffered_logs), schedule_log_sending(buffered_logs))


if __name__ == "__main__":
    asyncio.run(main())
