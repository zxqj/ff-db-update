#! /bin/bash

uv tool uninstall slay-db-update
./clean.sh
uv build
uv tool install --no-cache .
