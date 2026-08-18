#!/bin/bash
# Stop all SAPE agents and frontend (Git Bash en Windows: kill por puerto).
#
# En Windows los PID de bash (MSYS) no coinciden con los PID de Windows, así que
# el método confiable es matar por puerto: netstat localiza el PID real y
# taskkill lo termina (con su árbol de procesos).
set -uo pipefail

LOG_DIR="/tmp/sape_logs"
PIDS_FILE="$LOG_DIR/agent_pids.txt"
PORTS=(8000 8001 8002 8003 8004 8006 8007 8080 4200)

# Puertos → PID de Windows vía netstat (los PID de bash/MSYS no coinciden con
# los de Windows, así que kill/lsof no sirven acá — hay que usar taskkill).
kill_port() {
    local port=$1 pid
    for pid in $(netstat -ano 2>/dev/null | awk -v p=":${port}\$" '$4=="LISTENING" && $2 ~ p {print $5}' | sort -u); do
        if [[ -n "$pid" && "$pid" != "0" ]]; then
            echo "  Killing port $port (PID $pid)"
            taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
        fi
    done
}

echo "Stopping SAPE agents..."
for port in "${PORTS[@]}"; do
    kill_port "$port"
done
rm -f "$PIDS_FILE"
echo "Done."

rm -f "$PIDS_FILE"
echo "Listo."
