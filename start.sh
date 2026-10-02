#!/usr/bin/env bash
#
# Bash equivalent of start.ps1 for macOS/Linux.
#
# Usage:
#   ./start.sh [--provider fake|local|openai|openrouter] [--setup] [--check-only] [--debug-trace]
#
set -euo pipefail

PROVIDER="fake"
EXPLICIT_PROVIDER=false
SETUP=false
CHECK_ONLY=false
DEBUG_TRACE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --provider)
            EXPLICIT_PROVIDER=true
            PROVIDER="$2"
            shift 2
            ;;
        --provider=*)
            EXPLICIT_PROVIDER=true
            PROVIDER="${1#*=}"
            shift
            ;;
        --setup)
            SETUP=true
            shift
            ;;
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        --debug-trace)
            DEBUG_TRACE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--provider fake|local|openai|openrouter] [--setup] [--check-only] [--debug-trace]"
            echo ""
            echo "  --setup        Create .venv if needed, install backend and locked frontend dependencies, then start."
            echo "  --check-only   Validate prerequisites, model configuration and persistence without starting servers."
            echo "  --provider     LLM adapter (default: fake). Omit it when LLM_CONFIG_PATH selects model profiles."
            echo "  --debug-trace  Write a sensitive JSONL trace to logs/debug.log."
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

case "$PROVIDER" in
    fake|local|openai|openrouter) ;;
    *)
        echo "Invalid --provider '$PROVIDER'. Expected one of: fake, local, openai, openrouter." >&2
        exit 1
        ;;
esac

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_ROOT="$PROJECT_ROOT/frontend"
VENV_DIR="$PROJECT_ROOT/.venv"
LOGS_ROOT="$PROJECT_ROOT/logs"
COMPOSE_PATH="$PROJECT_ROOT/compose.yaml"
DEBUG_TRACE_PATH_VALUE="$LOGS_ROOT/debug.log"

API_PID=""
UI_PID=""
API_OUTPUT_LOG=""
API_ERROR_LOG=""
UI_OUTPUT_LOG=""
UI_ERROR_LOG=""

step() {
    printf '\033[36m[startup] %s\033[0m\n' "$1"
}

fail() {
    printf '\033[31m%s\033[0m\n' "$1" >&2
    exit 1
}

resolve_venv_python() {
    for env_root in "$VENV_DIR" "$PROJECT_ROOT/.venv-uv"; do
        for rel in "bin/python" "Scripts/python.exe"; do
            local candidate="$env_root/$rel"
            if [[ -x "$candidate" ]]; then
                if "$candidate" -c "import sys; raise SystemExit(0)" >/dev/null 2>&1; then
                    echo "$candidate"
                    return 0
                fi
            fi
        done
    done
    return 1
}

new_virtual_environment() {
    local python_bin=""
    for name in python3.12 python3 python; do
        if command -v "$name" >/dev/null 2>&1; then
            python_bin="$(command -v "$name")"
            break
        fi
    done
    [[ -n "$python_bin" ]] || fail "Python 3.12 was not found. Install it, then run ./start.sh --setup again."

    step "Creating Python virtual environment..."
    "$python_bin" -m venv "$VENV_DIR" || fail "Python failed to create .venv. Confirm Python 3.12 or newer is installed."
}

resolve_node_tools() {
    local node_path="" npm_path=""
    command -v node >/dev/null 2>&1 && node_path="$(command -v node)"
    command -v npm >/dev/null 2>&1 && npm_path="$(command -v npm)"

    if { [[ -z "$node_path" ]] || [[ -z "$npm_path" ]]; } && [[ -d "$PROJECT_ROOT/.tools" ]]; then
        local portable_node
        portable_node="$(find "$PROJECT_ROOT/.tools" -type f -name node 2>/dev/null | head -n 1)"
        if [[ -n "$portable_node" ]]; then
            node_path="$portable_node"
            local portable_npm
            portable_npm="$(dirname "$portable_node")/npm"
            [[ -x "$portable_npm" ]] && npm_path="$portable_npm"
        fi
    fi

    [[ -n "$node_path" && -n "$npm_path" ]] || fail "Node.js 22 and npm were not found. Install Node.js 22, then rerun the command."

    NODE_PATH_BIN="$node_path"
    NPM_PATH_BIN="$npm_path"
}

wait_for_url() {
    local name="$1" url="$2" pid="$3" timeout_seconds="${4:-30}"
    local deadline=$((SECONDS + timeout_seconds))

    while (( SECONDS < deadline )); do
        if ! kill -0 "$pid" 2>/dev/null; then
            fail "$name stopped during startup. Check the logs for details."
        fi
        if curl --silent --fail --max-time 2 --output /dev/null "$url"; then
            return 0
        fi
        sleep 0.3
    done

    fail "$name did not become ready at $url within $timeout_seconds seconds."
}

stop_process() {
    local pid="$1"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        for _ in $(seq 1 50); do
            kill -0 "$pid" 2>/dev/null || return 0
            sleep 0.1
        done
        kill -9 "$pid" 2>/dev/null || true
    fi
}

show_log_tail() {
    local label="$1" path="$2" lines="${3:-25}"
    [[ -n "$path" && -f "$path" ]] || return 0
    [[ -s "$path" ]] || return 0

    echo ""
    printf '\033[33m----- %s (last %s lines) -----\033[0m\n' "$label" "$lines"
    tail -n "$lines" "$path"
    printf '\033[33m----- end %s -----\033[0m\n' "$label"
}

get_persistence_target() {
    local python_path="$1"
    "$python_path" -m smb_requirement_agent.infrastructure.persistence.startup_check --target | tr -d '[:space:]'
}

test_persistence_ready() {
    local python_path="$1"
    "$python_path" -m smb_requirement_agent.infrastructure.persistence.startup_check --quiet >/dev/null 2>&1
}

wait_for_persistence() {
    local python_path="$1" timeout_seconds="${2:-30}"
    local deadline=$((SECONDS + timeout_seconds))

    while (( SECONDS < deadline )); do
        test_persistence_ready "$python_path" && return 0
        sleep 0.5
    done

    "$python_path" -m smb_requirement_agent.infrastructure.persistence.startup_check
    fail "PostgreSQL did not become ready within $timeout_seconds seconds."
}

cleanup() {
    local exit_code=$?
    set +e

    local api_died=false ui_died=false
    [[ -n "$API_PID" ]] && ! kill -0 "$API_PID" 2>/dev/null && api_died=true
    [[ -n "$UI_PID" ]] && ! kill -0 "$UI_PID" 2>/dev/null && ui_died=true

    if (( exit_code != 0 )) && { $api_died || $ui_died; }; then
        echo ""
        printf '\033[31mStartup failed. Showing the last log lines so you can see the real cause:\033[0m\n'
        show_log_tail "API stderr" "$API_ERROR_LOG"
        show_log_tail "API stdout" "$API_OUTPUT_LOG"
        show_log_tail "Review UI stderr" "$UI_ERROR_LOG"
        show_log_tail "Review UI stdout" "$UI_OUTPUT_LOG"
    fi

    [[ -n "$UI_PID" ]] && stop_process "$UI_PID"
    [[ -n "$API_PID" ]] && stop_process "$API_PID"

    exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

cd "$PROJECT_ROOT"

if $SETUP && ! resolve_venv_python >/dev/null; then
    new_virtual_environment
fi

PYTHON_PATH="$(resolve_venv_python)" || fail "The .venv environment is missing. Run ./start.sh --setup first."

resolve_node_tools

if $SETUP; then
    step "Installing backend dependencies..."
    "$PYTHON_PATH" -m pip install -e ".[dev]"

    step "Installing locked frontend dependencies..."
    (cd "$FRONTEND_ROOT" && "$NPM_PATH_BIN" ci)
fi

VITE_SCRIPT="$FRONTEND_ROOT/node_modules/vite/bin/vite.js"
[[ -f "$VITE_SCRIPT" ]] || fail "Frontend dependencies are missing. Run ./start.sh --setup first."

export LLM_PROVIDER="$PROVIDER"
if $DEBUG_TRACE; then
    export DEBUG_TRACE_ENABLED="true"
    export DEBUG_TRACE_PATH="$DEBUG_TRACE_PATH_VALUE"
fi

step "Validating model configuration..."
PROFILE_CHECK_ARGS=()
if [[ "$EXPLICIT_PROVIDER" == "true" ]]; then PROFILE_CHECK_ARGS=(--explicit-provider "$PROVIDER"); fi
"$PYTHON_PATH" -m smb_requirement_agent.interfaces.cli.llm check "${PROFILE_CHECK_ARGS[@]}"

PERSISTENCE_TARGET="$(get_persistence_target "$PYTHON_PATH")"

if $CHECK_ONLY; then
    step "Checking persistence readiness..."
    "$PYTHON_PATH" -m smb_requirement_agent.infrastructure.persistence.startup_check
    step "Startup prerequisites and configuration are valid."
    trap - EXIT
    exit 0
fi

step "Checking local API and UI ports..."
"$PYTHON_PATH" "$PROJECT_ROOT/scripts/check_ports.py" --port "API=8000" --port "Review UI=5173" \
    || fail "Free the port above, then rerun ./start.sh."

if [[ "$PERSISTENCE_TARGET" == "local-postgres" ]]; then
    if ! test_persistence_ready "$PYTHON_PATH"; then
        DOCKER_PATH="$(command -v docker || true)"
        [[ -n "$DOCKER_PATH" ]] || fail "Local PostgreSQL is not ready and Docker was not found. Install/start Docker Desktop, or set PERSISTENCE_PROVIDER=memory."
        step "Starting local PostgreSQL with Docker Compose..."
        "$DOCKER_PATH" compose --file "$COMPOSE_PATH" up --detach postgres
        step "Waiting for PostgreSQL to become ready..."
        wait_for_persistence "$PYTHON_PATH"
    fi
elif [[ "$PERSISTENCE_TARGET" == "external-postgres" ]]; then
    step "Checking external PostgreSQL readiness..."
    "$PYTHON_PATH" -m smb_requirement_agent.infrastructure.persistence.startup_check
fi

if [[ "$PERSISTENCE_TARGET" != "memory" ]]; then
    step "Applying pending database migrations..."
    "$PYTHON_PATH" -m smb_requirement_agent.infrastructure.persistence.migrate
fi

mkdir -p "$LOGS_ROOT"
RUN_TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
API_OUTPUT_LOG="$LOGS_ROOT/api-$RUN_TIMESTAMP.log"
API_ERROR_LOG="$LOGS_ROOT/api-error-$RUN_TIMESTAMP.log"
UI_OUTPUT_LOG="$LOGS_ROOT/ui-$RUN_TIMESTAMP.log"
UI_ERROR_LOG="$LOGS_ROOT/ui-error-$RUN_TIMESTAMP.log"

step "Starting API on http://127.0.0.1:8000..."
"$PYTHON_PATH" -m uvicorn smb_requirement_agent.interfaces.api.main:app --host 127.0.0.1 --port 8000 \
    >"$API_OUTPUT_LOG" 2>"$API_ERROR_LOG" &
API_PID=$!
wait_for_url "API" "http://127.0.0.1:8000/health" "$API_PID"

step "Starting review UI on http://127.0.0.1:5173..."
(cd "$FRONTEND_ROOT" && exec "$NODE_PATH_BIN" "$VITE_SCRIPT" --host 127.0.0.1 --port 5173 \
    >"$UI_OUTPUT_LOG" 2>"$UI_ERROR_LOG") &
UI_PID=$!
wait_for_url "Review UI" "http://127.0.0.1:5173" "$UI_PID"

echo ""
printf '\033[32mApplication ready\033[0m\n'
echo "  Review UI:  http://127.0.0.1:5173"
echo "  API docs:   http://127.0.0.1:8000/docs"
echo "  Health:     http://127.0.0.1:8000/health"
echo "  Provider:   $PROVIDER"
echo "  API log:    $API_OUTPUT_LOG"
echo "  API errors: $API_ERROR_LOG"
echo "  UI log:     $UI_OUTPUT_LOG"
echo "  UI errors:  $UI_ERROR_LOG"
if $DEBUG_TRACE; then
    echo "  Debug trace: $DEBUG_TRACE_PATH_VALUE"
    echo "  WARNING: includes requirement text and final LLM completions."
fi
echo ""
echo "Press Ctrl+C to stop both servers."

while kill -0 "$API_PID" 2>/dev/null && kill -0 "$UI_PID" 2>/dev/null; do
    sleep 0.5
done

if ! kill -0 "$API_PID" 2>/dev/null; then
    fail "API stopped unexpectedly."
fi
fail "Review UI stopped unexpectedly."
