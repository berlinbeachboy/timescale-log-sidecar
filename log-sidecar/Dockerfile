ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG VERSION=dev

# Create a user cap-on
RUN addgroup --system --gid 10001 cap-on \
 && adduser  --system --uid 10001 --ingroup cap-on cap-on

# Get and install logging sidecar
RUN mkdir -p /log-sidecar
WORKDIR /log-sidecar/

# install python dependencies
RUN pip install --upgrade pip
RUN pip install asyncpg==0.31.0 tenacity==8.3.0


COPY . /log-sidecar
COPY --chown=cap-on:cap-on . /log-sidecar

USER cap-on

ENV PYTHONPATH=/log-sidecar
ENV VERSION=$VERSION

CMD ["python", "start.py"]