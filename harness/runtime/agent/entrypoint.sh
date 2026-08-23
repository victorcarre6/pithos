#!/bin/sh
set -eu

mkdir -p /tmp/home /tmp/pi-config
cp -R /pi-config-source/. /tmp/pi-config/

exec pi "$@"
