#!/bin/bash
# Stop all SAPE agents and frontend (Git Bash en Windows: kill por puerto).
#
# En Windows los PID de bash (MSYS) no coinciden con los PID de Windows, así que
# el método confiable es matar por puerto: netstat localiza el PID real y
# taskkill lo termina (con su árbol de procesos).
set -uo pipefail

LOG_DIR="/tmp/sape_logs"
PIDS_FILE="$LOG_DIR/agent_pids.txt"
PORTS=(8000 8001 8002 8003 8004 8006 8080 4200)

pids_on_port() {
    local port=$1
    netstat -ano 2>/dev/null \
        | awk -v patt=":${port}\$" '$4=="LISTENING" && $2 ~ patt {print $5}' \
        | sort -u
}

echo "Frenando servicios SAPE..."
for port in "${PORTS[@]}"; do
    for pid in $(pids_on_port "$port"); do
        if [[ -n "$pid" && "$pid" != "0" ]]; then
            echo "  Matando puerto $port (PID $pid)"
            taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
        fi
    done
done

rm -f "$PIDS_FILE"
echo "Listo."
