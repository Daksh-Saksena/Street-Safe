set -euo pipefail
SCENARIO="${1:-clear}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
if [[ -f "$VENV/bin/activate" ]]; then
  source "$VENV/bin/activate"
fi
export PYTHONPATH="$ROOT"
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║        StreetSafe — Demo Launcher                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "[1/3] Starting FastAPI backend on http://localhost:8000 ..."
cd "$ROOT/backend"
python server.py &
BACKEND_PID=$!
echo -n "    Waiting for backend"
for i in $(seq 1 15); do
  sleep 1
  if curl -sf http://localhost:8000/ >/dev/null 2>&1; then
    echo " ready ✓"
    break
  fi
  echo -n "."
  if [[ $i -eq 15 ]]; then
    echo " (timeout — backend may be slow to start)"
  fi
done
echo "[2/3] Serving frontend map on http://localhost:9000 ..."
cd "$ROOT/frontend"
python -m http.server 9000 --bind 127.0.0.1 &>/dev/null &
FRONTEND_PID=$!
echo "    Open: http://localhost:9000"
cd "$ROOT/pi"
if [[ "$SCENARIO" == "demo" ]]; then
  echo "[3/3] Running guided demo script (demo_scenarios.py) ..."
  echo ""
  python demo_scenarios.py
else
  echo "[3/3] Running drone control loop (scenario=$SCENARIO) ..."
  echo ""
  python main.py --scenario "$SCENARIO"
fi
echo ""
echo "Stopping backend and frontend servers..."
kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
echo "All processes stopped."

echo "╔══════════════════════════════════════════════════╗"
echo "║        StreetSafe — Demo Launcher                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "[1/3] Starting FastAPI backend on http://localhost:8000 ..."
cd "$ROOT/backend"
python server.py &
BACKEND_PID=$!
echo -n "    Waiting for backend"
for i in $(seq 1 15); do
  sleep 1
  if curl -sf http://localhost:8000/ >/dev/null 2>&1; then
    echo " ready ✓"
    break
  fi
  echo -n "."
  if [[ $i -eq 15 ]]; then
    echo " (timeout — backend may be slow to start)"
  fi
done
echo "[2/3] Serving frontend map on http://localhost:9000 ..."
cd "$ROOT/frontend"
python -m http.server 9000 --bind 127.0.0.1 &>/dev/null &
FRONTEND_PID=$!
echo "    Open: http://localhost:9000"
cd "$ROOT/pi"
if [[ "$SCENARIO" == "demo" ]]; then
  echo "[3/3] Running guided demo script (demo_scenarios.py) ..."
  echo ""
  python demo_scenarios.py
else
  echo "[3/3] Running drone control loop (scenario=$SCENARIO) ..."
  echo ""
  python main.py --scenario "$SCENARIO"
fi
echo ""
echo "Stopping backend and frontend servers..."
kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
echo "All processes stopped."
