#!/bin/bash
# ==============================================================================
# SAPE — Start All Agents + Frontend
# Usage: ./start_all.sh [--skip-frontend]
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKIP_FRONTEND=false
if [[ "$1" == "--skip-frontend" ]]; then
    SKIP_FRONTEND=true
fi

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Each entry: "name:port:dir:command"
# command is invoked with bash -c from within dir, stdout/stderr → log
readonly AGENTS=(
    "orchestrator:8000:$SCRIPT_DIR/agente_orchestrator:.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000"
    "job_description:8001:$SCRIPT_DIR/agente_job_description:.venv/bin/python server.py"
    "busquedas_internas:8002:$SCRIPT_DIR/agente_busquedas_internas:.venv/bin/python server.py"
    "entrevistas:8003:$SCRIPT_DIR/agente_entrevistas:.venv/bin/python server.py"
    "scheduling:8004:$SCRIPT_DIR/agente_scheduling:.venv/bin/python server.py"
    "busquedas_externas:8080:$SCRIPT_DIR/agente_busquedas_externas:.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8080"
)
readonly FRONTEND_DIR="$SCRIPT_DIR/frontend"
readonly FRONTEND_PORT=4200
readonly LOG_DIR="/tmp/sape_logs"
readonly TIMEOUT=30

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo -e "\033[1;34m[INFO]\033[0m  $1"; }
ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $1"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m $1"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m $1"; exit 1; }

clear_port() {
    local port=$1
    local pid=$(lsof -ti :$port 2>/dev/null || true)
    if [[ -n "$pid" ]]; then
        warn "Port $port in use (PID $pid) — killing"
        kill $pid 2>/dev/null || true
        sleep 1
    fi
}

wait_for_health() {
    local port=$1
    local name=$2
    local count=0
    while [[ $count -lt $TIMEOUT ]]; do
        if curl -sf --max-time 2 "http://localhost:$port/health" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
        ((count++))
    done
    return 1
}

# ---------------------------------------------------------------------------
# Pre-flight: clear ports
# ---------------------------------------------------------------------------
info "Clearing ports..."
for port in 8000 8001 8002 8003 8004 8080 $FRONTEND_PORT; do
    clear_port $port
done
sleep 2
ok "Ports clear"

# ---------------------------------------------------------------------------
# Create log dir
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR"/agent_pids.txt

# ---------------------------------------------------------------------------
# Start agents
# ---------------------------------------------------------------------------
info "Starting agents..."
for entry in "${AGENTS[@]}"; do
    # Split on first colon: name:port:dir:command
    name="${entry%%:*}"
    rest="${entry#*:}"
    port="${rest%%:*}"
    rest="${rest#*:}"
    dir="${rest%%:*}"
    cmd="${rest#*:}"  # everything after the third colon

    log="$LOG_DIR/${name}.log"

    (
        cd "$dir"
        setsid bash -c "$cmd" >> "$log" 2>&1 &
    )

    echo "$port:$name:$!" >> "$LOG_DIR/agent_pids.txt"
    info "  Started $name on :$port (log: $log)"
done

# ---------------------------------------------------------------------------
# Wait for all agents healthy
# ---------------------------------------------------------------------------
info "Waiting for agents to be healthy..."
while IFS=':' read -r port name pid; do
    if ! wait_for_health "$port" "$name"; then
        fail "Agent $name on port $port never became healthy (check $LOG_DIR/${name}.log)"
    fi
    ok "  $name (:$port) healthy"
done < "$LOG_DIR/agent_pids.txt"

info "All agents healthy ✅"

# ---------------------------------------------------------------------------
# Start frontend
# ---------------------------------------------------------------------------
if [[ "$SKIP_FRONTEND" == "false" ]]; then
    info "Starting Angular frontend on :$FRONTEND_PORT..."

    # Check if node_modules exists
    if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
        warn "node_modules not found — running npm install..."
        (
            cd "$FRONTEND_DIR"
            npm install
        )
    fi

    log="$LOG_DIR/frontend.log"
    (
        cd "$FRONTEND_DIR"
        setsid npm run start -- --port $FRONTEND_PORT >> "$log" 2>&1 &
    )
    echo "$FRONTEND_PORT:frontend:$!" >> "$LOG_DIR/agent_pids.txt"

    info "Waiting for frontend on :$FRONTEND_PORT..."
    count=0
    while [[ $count -lt 90 ]]; do
        if curl -sf --max-time 2 "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
            ok "Frontend ready at http://localhost:$FRONTEND_PORT"
            break
        fi
        sleep 2
        ((count+=2))
        if [[ $((count % 20)) -eq 0 ]]; then
            info "  Still starting... ($count s)"
        fi
    done
    if [[ $count -ge 90 ]]; then
        warn "Frontend may not be ready — check $log"
    fi
fi

info ""
info "========================================"
ok  "SAPE is running!"
info "========================================"
[[ "$SKIP_FRONTEND" == "false" ]] && info "  Frontend:  http://localhost:$FRONTEND_PORT"
info "  Orchestr:  http://localhost:8000"
info "  JD Agent:  http://localhost:8001"
info "  Int Agent: http://localhost:8002"
info "  Ent Agent: http://localhost:8003"
info "  Sch Agent: http://localhost:8004"
info "  Ext Agent: http://localhost:8080"
info ""
info "Logs: $LOG_DIR/*.log"
info ""
info "To stop: ./stop_all.sh"