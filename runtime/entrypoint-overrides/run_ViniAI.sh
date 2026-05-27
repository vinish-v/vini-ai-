#!/bin/bash

. "/ins/setup_venv.sh" "$@"
. "/ins/copy_A0.sh" "$@"

echo "Starting Vini AI bootstrap manager..."
exec /opt/venv-a0/bin/python /exe/self_update_manager.py docker-run-ui
