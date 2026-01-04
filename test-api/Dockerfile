ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a user cap-on
RUN addgroup --system --gid 10001 cap-on \
 && adduser  --system --uid 10001 --ingroup cap-on cap-on

# Get and install logging sidecar
RUN mkdir -p /test-api
WORKDIR /test-api/

# install python dependencies
RUN pip install --upgrade pip
RUN pip install asyncpg==0.31.0 fastapi==0.121.2 uvicorn==0.40.0 pytest==9.0.2 pytest-asyncio==1.3.0 httpx==0.28.1

COPY . /test-api

ENV PYTHONPATH=/test-api