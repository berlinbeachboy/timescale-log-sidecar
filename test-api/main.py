from fastapi import FastAPI
from logger import LoggingHTTPMiddleware, logger
from starlette.requests import Request
from starlette.responses import JSONResponse

fastapi = FastAPI(title="Log-SideCar Test API", version="0.1.0")

fastapi.add_middleware(LoggingHTTPMiddleware)


async def handle_value_error(request: Request, exc: ValueError):
    username = request.state.username if hasattr(request.state, "username") else None
    logger.error(exc, {"trace_id": request.state.trace_id, "username": username})
    return JSONResponse(
        status_code=400,
        content={"message": f"ValueError. {exc}."},
    )


@fastapi.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    return await handle_value_error(request, exc)


@fastapi.get("/hello")
async def hello_world():
    return JSONResponse(status_code=200, content="Hello World")


@fastapi.get("/log_hello")
async def hello_world_log():
    logger.info("Hello World")
    return JSONResponse(status_code=200, content="Hello World")


@fastapi.get("/log_error")
async def error_log():
    raise ValueError("Test-Error")
