#!/usr/bin/env bash
# Start the Python core (:8000). Optional: ./run.sh gateway  -> also start the Java gateway (:8080)
set -e
cd "$(dirname "$0")"
python3 -m echo_code &
CORE=$!
trap 'kill $CORE 2>/dev/null' EXIT
if [ "$1" = "gateway" ]; then
  sleep 1
  java java/EchoGateway.java
else
  wait $CORE
fi
