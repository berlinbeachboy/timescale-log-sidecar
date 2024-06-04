# timescale-log-sidecar
A sidecar container collecting access &amp; application logs via a named pipe and sending to TimescaleDB / Postgres

## What does it do

This application is supposed to run as a sidecar container (on same host / pod) to another application, supposedly an API.
An example on how to use this is given in the `test-api` folder which also includes tests.

There is a ready-built docker image [here](https://hub.docker.com/repository/docker/phratz/ts-log-sidecar/general).

The application/api whose logs you want to collect, needs to send logs in JSON format to a named FIFO pipe 
which is specified in the environment variables.
This container reads the logs and sends them to a Postgres / Timescale using asyncpg.

There are two tables this can send data to:

### access_logs
```postgresql
CREATE TABLE IF NOT EXISTS ${ACCESS_LOG_TABLE} (
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
    response_size          INTEGER           NOT NULL,
    duration               NUMERIC(9,3)      NOT NULL,
    data                   JSONB             NULL,
    PRIMARY KEY(time, trace_id));
```

### application_logs
```postgresql
CREATE TABLE IF NOT EXISTS ${APPLICATION_LOG_TABLE} (
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
    PRIMARY KEY(time, trace_id));
```

Unfortunately, right now there is no (non-coding) way to consider custom fields or DB columns.
JSON key/value other than the ones fitting the tables above are currently disregarded.
Feel free to fork this and adapt it to fit your needs.

## Getting started

Ensure there is an accessible TimescaleDB running and set the environment variables accordingly.
An overview which environment variables are needed is given in `.env.example`.

The setup needs to be run as postgres superuser, i.e `POSTGRES_USER`. 
Once it's setup you should only use the `LOG_DB_USER` user 
which does not have all privileges.

The `log-sidecar/start.py` would also be the entrypoint for any Docker container.
Currently, working on getting this up on Docker hub.

## Testing 

**WARNING**: Running the tests will truncate your database. 
Please ensure you're using this locally/in DEV only.

```bash
docker-compose -f docker-compose.test.yml up --build
```
will start your testing environment.
Make sure you setup the DB when starting the first time by setting `SETUP_DB` to 1 in your `.env` file.
You can then enter the container and start the tests with pytest in the test-api directory.

## Credits

Heavily inspired by this blog [entry](https://www.komu.engineer/blogs/timescaledb/timescaledb-for-logs).
