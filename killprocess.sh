#!/bin/bash

# Find and kill processes listening on ports 8000 and 8001
ports=(8000 8001 8002)

for port in "${ports[@]}"; do
  pids=$(lsof -t -i:$port)
  if [ -n "$pids" ]; then
    echo "Killing processes on port $port: $pids"
    kill -9 $pids
  else
    echo "No process found on port $port"
  fi
done
