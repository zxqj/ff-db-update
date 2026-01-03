#! /bin/bash

uv tool uninstall slay-db-update
rm -r build dist *.egg-info
uv build
uv tool install --no-cache .
