#!/usr/bin/env sh
set -eu

# 默认值，可被环境变量覆盖
: "${BIND_ADDR:=0.0.0.0:5000}"
: "${GUNICORN_WORKERS:=4}"
: "${GUNICORN_TIMEOUT:=120}"

echo "Starting gunicorn on ${BIND_ADDR} with workers=${GUNICORN_WORKERS}, timeout=${GUNICORN_TIMEOUT}"

# 用 exec 让 gunicorn 接管 PID 1，正确处理信号与日志
exec gunicorn \
  --bind "${BIND_ADDR}" \
  --workers "${GUNICORN_WORKERS}" \
  --timeout "${GUNICORN_TIMEOUT}" \
  main:app