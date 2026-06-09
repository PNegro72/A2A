#!/bin/bash
# Stop all SAPE agents and frontend
LOG_DIR="/tmp/sape_logs"
PIDS_FILE="$LOG_DIR/agent_pids.txt"

if [[ -f "$PIDS_FILE" ]]; then
    echo "Stopping SAPE agents..."
    while IFS=':' read -r port name pid; do
        if [[ -n "$pid" ]] && kill -0 $pid 2>/dev/null; then
            echo "  Killing $name (PID $pid, port $port)"
            kill $pid 2>/dev/null || true
        fi
    done < "$PIDS_FILE"
    rm -f "$PIDS_FILE"
    echo "Done."
else
    echo "No PID file found. Killing by port..."
    for port in 8000 8001 8002 8003 8004 8080 4200; do
        pid=$(lsof -ti :$port 2>/dev/null || true)
        if [[ -n "$pid" ]]; then
            echo "  Killing port $port (PID $pid)"
            kill $pid 2>/dev/null || true
        fi
    done
fi
echo "All stopped."