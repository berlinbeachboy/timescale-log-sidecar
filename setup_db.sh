#!/usr/bin/env bash

export PGPASSWORD="${POSTGRES_PASSWORD}"

create_extension() {
     psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
}

create_access_log_table() {
    psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" -c "CREATE TABLE IF NOT EXISTS ${ACCESS_LOG_TABLE} (
    time                   TIMESTAMP         NOT NULL,
    application_name       VARCHAR(20)       NOT NULL,
    environment_name       VARCHAR(10)       NOT NULL,
    trace_id               VARCHAR(36)       NOT NULL,
    host_ip                VARCHAR(20)       NOT NULL,
    remote_ip_address      VARCHAR(30)       NOT NULL,
    username               VARCHAR(30)       NOT NULL,
    request_method         VARCHAR(5)        NOT NULL,
    request_path           TEXT              NOT NULL,
    response_status        SMALLINT          NOT NULL,
    duration               NUMERIC(9,3)      NOT NULL,
    data                   JSONB             NULL,
    PRIMARY KEY(time, trace_id)
    );"
}

create_application_log_table() {
    psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" -c "CREATE TABLE IF NOT EXISTS ${APPLICATION_LOG_TABLE} (
    time                   TIMESTAMP         NOT NULL,
    application_name       VARCHAR(20)       NOT NULL,
    environment_name       VARCHAR(10)       NOT NULL,
    trace_id               VARCHAR(36)       NOT NULL,
    host_ip                VARCHAR(20)       NOT NULL,
    username               VARCHAR(30)       NOT NULL,
    level                  VARCHAR(10)       NOT NULL,
    file_path              TEXT              NOT NULL,
    message                TEXT              NOT NULL,
    data                   JSONB             NULL,
    PRIMARY KEY(time, trace_id)
    );"
}

create_access_table_indices() {

    #psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" -c "CREATE INDEX idxgin ON ${ACCESS_LOG_TABLE} USING GIN (data);"
    psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" -c "CREATE INDEX ON ${ACCESS_LOG_TABLE} (request_path, trace_id, time DESC) WHERE request_path IS NOT NULL AND trace_id IS NOT NULL;"
}

create_application_table_indices() {

    psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" -c "CREATE INDEX ON ${APPLICATION_LOG_TABLE} (level, trace_id, time DESC) WHERE level IS NOT NULL AND trace_id IS NOT NULL;"
}


create_hypertables() {
    psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
    -c "SELECT create_hypertable('${ACCESS_LOG_TABLE}', 'time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 Month');"

    psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
    -c "SELECT create_hypertable('${APPLICATION_LOG_TABLE}', 'time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 Month');"
}


create_user_and_give_permission() {
  psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -c \
  """
  DO
  \$do\$
  BEGIN
    IF EXISTS (
        SELECT FROM pg_catalog.pg_roles
        WHERE  rolname = '${LOG_DB_USER}') THEN

        RAISE NOTICE 'Role ${LOG_DB_USER} already exists. Skipping.';
     ELSE
        CREATE ROLE ${LOG_DB_USER} LOGIN PASSWORD '${LOG_DB_PASSWORD}';
     END IF;
  END
  \$do\$;
  """

  psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" -c "GRANT INSERT, UPDATE, SELECT ON TABLE ${ACCESS_LOG_TABLE} TO ${LOG_DB_USER};"
  psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" -c "GRANT INSERT, UPDATE, SELECT ON TABLE ${APPLICATION_LOG_TABLE} TO ${LOG_DB_USER};"
  echo "Made User ${LOG_DB_USER} and gave permissions on tables ${ACCESS_LOG_TABLE} and ${APPLICATION_LOG_TABLE}"
}

#create_extension # Uncomment if you don't have timescaledb installed
create_access_log_table
create_application_log_table
create_access_table_indices
create_application_table_indices
create_hypertables
create_user_and_give_permission