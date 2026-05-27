#!/bin/bash

. "/ins/setup_venv.sh" "$@"
. "/ins/copy_A0.sh" "$@"

if [ -d /opt/vini-bundled-plugins/_vini_canvas ]; then
  mkdir -p /a0/usr/plugins
  rm -rf /a0/usr/plugins/_vini_canvas
  cp -R /opt/vini-bundled-plugins/_vini_canvas /a0/usr/plugins/_vini_canvas
fi

echo "Starting Vini AI bootstrap manager..."
exec /opt/venv-a0/bin/python /exe/self_update_manager.py docker-run-ui
