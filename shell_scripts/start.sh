#! /usr/bin/env bash

set -e

python /log-sidecar/wait_for_db.py

if [ "$SETUP_DB" = "1" ]; then
    echo "SETUP env variable is set. Creating data base."
    . /log-sidecar/shell_scripts/setup_db.sh
else
    echo "Skipping DB setup."
fi

python /log-sidecar/main.py