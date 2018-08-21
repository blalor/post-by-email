#!/bin/bash

set -e -u

export LD_LIBRARY_PATH="$( scl enable python27 'echo ${LD_LIBRARY_PATH}' )"
export PATH="$( scl enable python27 'echo ${PATH}' )"
export PKG_CONFIG_PATH="$( scl enable python27 'echo ${PKG_CONFIG_PATH}' )"

cd /post_by_email/

./clone.py

# --statsd-host STATSD_ADDR
exec gunicorn \
    --bind :5000 \
    --timeout 180 \
    --access-logfile /var/log/post-by-email/access.log \
    --workers 2 \
    FlaskApp:app
