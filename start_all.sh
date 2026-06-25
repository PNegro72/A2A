#!/bin/bash
# ==============================================================================
# SAPE — Start All Agents + Frontend
# Usage: ./start_all.sh [--skip-frontend]
#
# Compatible con Git Bash en Windows (sin setsid/lsof): usa nohup para
# backgroundear, netstat+taskkill para liberar puertos, y resuelve el python
# del venv en .venv/Scripts/python.exe (Windows) o .venv/bin/python (Linux).
# ==============================================================================

set -uo pipefail

# Forzar UTF-8 en stdout/stderr de los procesos hijos. Con la salida redirigida
# a archivos de log, Python usa cp1252 por defecto en Windows y crashea al
# imprimir caracteres no-ASCII (ej. '→' en los prints de observability.py).
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKIP_FRONTEND=false
if [[ "${1:-}" == "--skip-frontend" ]]; then
    SKIP_FRONTEND=true
fi

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Each entry: "name:port:dir:probe:command"
#   probe  = health  → readiness por GET /health
#            mcp     → readiness por GET /mcp (el server MCP no expone /health)
#   @PY@   se reemplaza por el python del venv del propio dir.
#
# rag_backend (Qdrant/) y mcp_server (MCP/) son la pila RAG que consume el
# agente de búsquedas internas: el backend habla con Qdrant Cloud, y el server
# MCP expone la tool `search` que el agente consume por HTTP en :8006/mcp.
readonly AGENTS=(
    "orchestrator:8000:$SCRIPT_DIR/agente_orchestrator:.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000"
    "job_description:8001:$SCRIPT_DIR/agente_job_description:.venv/bin/python server.py"
    "busquedas_internas:8002:$SCRIPT_DIR/agente_busquedas_internas:.venv/bin/python server.py"
    "entrevistas:8003:$SCRIPT_DIR/agente_entrevistas:.venv/bin/python server.py"
    "scheduling:8004:$SCRIPT_DIR/agente_scheduling:.venv/bin/python server.py"
    "busquedas_externas:8080:$SCRIPT_DIR/agente_busquedas_externas:.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8080"
)
readonly ALL_PORTS=(8000 8001 8002 8003 8004 8006 8080)
readonly FRONTEND_DIR="$SCRIPT_DIR/frontend"
readonly FRONTEND_PORT=4200
readonly LOG_DIR="/tmp/sape_logs"
readonly TIMEOUT=40

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo -e "\033[1;34m[INFO]\033[0m  $1"; }
ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $1"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m $1"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m $1"; exit 1; }

# PIDs (de Windows) que escuchan en un puerto, vía netstat.
pids_on_port() {
    local port=$1
    netstat -ano 2>/dev/null \
        | awk -v patt=":${port}\$" '$4=="LISTENING" && $2 ~ patt {print $5}' \
        | sort -u
}

clear_port() {
    local port=$1 pid
    for pid in $(pids_on_port "$port"); do
        if [[ -n "$pid" && "$pid" != "0" ]]; then
            warn "Port $port en uso (PID $pid) — matando"
            taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
        fi
    done
}

# Resuelve el python del venv de un dir (Windows: Scripts/, Linux: bin/).
venv_python() {
    local dir=$1
    if [[ -x "$dir/.venv/Scripts/python.exe" ]]; then
        echo ".venv/Scripts/python.exe"
    else
        echo ".venv/bin/python"
    fi
}

probe_ok() {
    local probe=$1 port=$2
    case "$probe" in
        mcp) curl -s  --max-time 2 -o /dev/null "http://localhost:$port/mcp"    >/dev/null 2>&1 ;;
        *)   curl -sf --max-time 2 -o /dev/null "http://localhost:$port/health" >/dev/null 2>&1 ;;
    esac
}

wait_for_ready() {
    local probe=$1 port=$2 count=0
    while [[ $count -lt $TIMEOUT ]]; do
        if probe_ok "$probe" "$port"; then return 0; fi
        sleep 1
        count=$((count + 1))
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
ok "Puertos liberados"

# ---------------------------------------------------------------------------
# Create log dir
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR/agent_pids.txt"

# ---------------------------------------------------------------------------
# Start agents
# ---------------------------------------------------------------------------
info "Arrancando servicios..."
for entry in "${AGENTS[@]}"; do
    # Split: name:port:dir:probe:cmd  (cmd es todo lo posterior al 4º ':')
    name="${entry%%:*}";  rest="${entry#*:}"
    port="${rest%%:*}";   rest="${rest#*:}"
    dir="${rest%%:*}";    rest="${rest#*:}"
    probe="${rest%%:*}";  cmd="${rest#*:}"

    if [[ ! -d "$dir" ]]; then
        fail "No existe el directorio de '$name': $dir"
    fi

    pyrel="$(venv_python "$dir")"
    if [[ ! -x "$dir/$pyrel" ]]; then
        fail "Falta el venv de '$name' ($dir/$pyrel). Crealo e instalá sus dependencias."
    fi
    cmd="${cmd//@PY@/$pyrel}"

    log="$LOG_DIR/${name}.log"
    ( cd "$dir" && exec nohup bash -c "$cmd" ) >> "$log" 2>&1 &
    pid=$!

    echo "$port:$name:$pid:$probe" >> "$LOG_DIR/agent_pids.txt"
    info "  $name → :$port (log: $log)"
done

# ---------------------------------------------------------------------------
# Wait for all agents healthy
# ---------------------------------------------------------------------------
info "Esperando readiness de los servicios..."
while IFS=':' read -r port name pid probe; do
    if ! wait_for_ready "$probe" "$port"; then
        fail "El servicio $name (:$port) nunca quedó listo (revisá $LOG_DIR/${name}.log)"
    fi
    ok "  $name (:$port) listo"
done < "$LOG_DIR/agent_pids.txt"

info "Todos los servicios listos ✅"

# ---------------------------------------------------------------------------
# Start frontend
# ---------------------------------------------------------------------------
if [[ "$SKIP_FRONTEND" == "false" ]]; then
    info "Arrancando frontend Angular en :$FRONTEND_PORT..."

    if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
        warn "node_modules ausente — corriendo npm install..."
        ( cd "$FRONTEND_DIR" && npm install )
    fi

    log="$LOG_DIR/frontend.log"
    ( cd "$FRONTEND_DIR" && exec nohup npm run start -- --port "$FRONTEND_PORT" ) >> "$log" 2>&1 &
    echo "$FRONTEND_PORT:frontend:$!:health" >> "$LOG_DIR/agent_pids.txt"

    info "Esperando frontend en :$FRONTEND_PORT..."
    count=0
    while [[ $count -lt 90 ]]; do
        if curl -sf --max-time 2 -o /dev/null "http://localhost:$FRONTEND_PORT"; then
            ok "Frontend listo en http://localhost:$FRONTEND_PORT"
            break
        fi
        sleep 2
        count=$((count + 2))
        if [[ $((count % 20)) -eq 0 ]]; then
            info "  Aún arrancando... ($count s)"
        fi
    done
    if [[ $count -ge 90 ]]; then
        warn "El frontend puede no estar listo — revisá $log"
    fi
fi

info ""
info "========================================"
ok  "SAPE corriendo!"
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
info "Para frenar: ./stop_all.sh"
