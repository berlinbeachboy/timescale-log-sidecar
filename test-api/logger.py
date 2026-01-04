import typing
import errno
import json
import os
import sys
import traceback
from datetime import datetime

from uuid import uuid4
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


RequestResponseEndpoint = typing.Callable[[Request], typing.Awaitable[Response]]
DispatchFunction = typing.Callable[[Request, RequestResponseEndpoint], typing.Awaitable[Response]]
LOCAL_IP = "your_ip"
LOG_PIPE = os.environ.get("NAMED_PIPE_FOLDER", "/tmp/namedPipes") + "/" + os.environ.get("NAMED_PIPE_FILE", "appLogs")
APPLICATION_NAME = os.environ.get("APPLICATION_NAME", "some_app")
ENV = os.environ.get("ENV", "DEV")


class LoggingHTTPMiddleware(BaseHTTPMiddleware):
    """(1) Logs all requests (and responses)
    (2) catches all uncaught exceptions and also logs them before returning a 500"""

    @staticmethod
    def format_access_log_dict(
            remote_ip_address=None,
            request_method=None,
            request_path=None,
            response_status=None,
            username=None,
            response_size=None,
            duration=None,
            data=None,
            trace_id=None,
            time=None,
    ):
        return {
            "type": "access",
            "application_name": APPLICATION_NAME,
            "environment_name": ENV,
            "trace_id": str(trace_id),
            "data": data,
            "username": username,
            "request_method": request_method,
            "request_path": request_path,
            "response_status": response_status,
            "response_size": response_size,
            "duration": duration,
            "time": str(time),
            "host_ip": LOCAL_IP,
            "remote_ip_address": remote_ip_address,
        }

    async def log_request_response(self, request: Request, response: Response, duration=None, username=None) -> None:
        """Logs access logs to named pipe or stout depending on ENV"""
        trace_id = uuid4() if not request.state.trace_id else request.state.trace_id
        time = request.state.time_started if request.state.time_started else datetime.utcnow()

        if ENV in ["STAG", "PROD", "TEST"]:
            try:
                log = self.format_access_log_dict(
                    remote_ip_address=request.client.host,
                    request_method=request.method,
                    request_path=request.url.path,
                    response_status=response.status_code,
                    response_size=response.headers.get("Content-Length"),
                    duration=duration,
                    username=username,
                    trace_id=trace_id,
                    time=time,
                )
                # we use newline to demarcate where one log event ends.
                write_data = json.dumps(log)
                write_data = write_data + "\n"
                write_data = write_data.encode()
                pipe = os.open(LOG_PIPE, os.O_WRONLY | os.O_NONBLOCK | os.O_ASYNC)
                os.write(pipe, write_data)
                os.close(pipe)
            except OSError as e:
                if e.errno == 6:
                    pass
                else:
                    pass
        elif ENV in ["TEST"]:
            pass
        else:
            logger.info(f"{request.method} {request.url.path} from {username}, responded with {response.status_code}")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.time_started = datetime.utcnow()
        request.state.trace_id = uuid4() if "X-trace-id" not in request.headers else request.headers["X-trace-id"]
        response: Response = Response(
            f"Internal server error. \n Trace_ID: {request.state.trace_id}",
            status_code=500,
        )
        try:
            response: Response = await call_next(request)
            return response
        except Exception as e:
            username = request.state.username if hasattr(request.state, "username") else None
            logger.error(
                e,
                {"trace_id": request.state.trace_id, "username": username},
                exc_info=True,
            )
            return response
        finally:
            username = request.state.username if hasattr(request.state, "username") else None
            duration = (datetime.utcnow() - request.state.time_started).total_seconds() * 1000
            await self.log_request_response(request, response, duration=duration, username=username)


def open_fifo(fifo_file):
    """ Open a Linux fifo file"""
    try:
        os.mkfifo(fifo_file, mode=0o777)
        print(f"Opened Pipe with address {fifo_file}")
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e
        print(f"Tried to open Pipe with address {fifo_file}, but it exists")
    return fifo_file


class DictFormatter(logging.Formatter):
    def __init__(self):
        logging.Formatter.__init__(self)
        self.ip = LOCAL_IP
        self.application_name = APPLICATION_NAME
        self.environment_name = ENV
        self.type = "application"

    @staticmethod
    def custom_format_exception(exception_info) -> str:
        return f"{type(exception_info[1]).__name__}: {str(exception_info[1])}"

    def format(self, record) -> str:
        time = datetime.utcnow()
        trace_id = record.args["trace_id"] if "trace_id" in record.args else None
        username = record.args["username"] if "username" in record.args else None
        file_path = record.args["file_path"] if "file_path" in record.args else record.pathname
        if record.exc_info:
            # If we're logging an exception, we need to resdet the file_path to where it occurred and reformat
            traces = traceback.extract_tb(record.exc_info[2])
            if traces[-1]:
                file_path = str(traces[-1].filename) + " | Line: " + str(traces[-1].lineno)
            if not record.exc_text:
                record.exc_text = self.custom_format_exception(record.exc_info)
        elif isinstance(record.msg, Exception):
            record.exc_text = f"{type(record.msg).__name__}: {str(record.msg)}"
        message = record.exc_text if record.exc_text else record.getMessage()
        log_dict = {
            "type": self.type,
            "application_name": self.application_name,
            "environment_name": self.environment_name,
            "trace_id": str(trace_id),
            "file_path": file_path,
            "level": record.levelname,
            "data": None,
            "time": str(time),
            "message": message,
            "host_ip": self.ip,
            "username": username,
        }
        return json.dumps(log_dict)


class NamedPipeHandler(logging.StreamHandler):
    """
    A custom handler that emits JSON output to a named pipe / fifo to emit logs to, they will be collected from there
    """

    def __init__(self, named_pipe=LOG_PIPE):
        logging.StreamHandler.__init__(self)
        self.fifo = open_fifo(named_pipe)

    def emit(self, record):
        try:
            log_json_str = self.format(record)
            write_data = log_json_str + "\n"
            write_data = write_data.encode()
            pipe = os.open(self.fifo, os.O_WRONLY | os.O_NONBLOCK | os.O_ASYNC)
            os.write(pipe, write_data)
            os.close(pipe)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            print(str(e))
            self.handleError(record)


logger = logging.getLogger("test-app")

if ENV in ["STAG", "PROD", "TEST"]:
    logger.setLevel(logging.INFO)
    handler = NamedPipeHandler()
    handler.setFormatter(DictFormatter())
else:
    handler = logging.StreamHandler(sys.stdout)
    logger.setLevel(logging.DEBUG)

logger.addHandler(handler)
