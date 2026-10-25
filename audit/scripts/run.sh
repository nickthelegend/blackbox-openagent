#!/bin/bash
set -euo pipefail
SLOT='/Volumes/Extreme SSD/Projects/grokbot/tools/heavy-slot.sh'
main_pid=''; copy_pid=''; copy_root=''; acquired=0
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$main_pid" ]; then kill "$main_pid" 2>/dev/null || true; wait "$main_pid" 2>/dev/null || true; fi
  if [ -n "$copy_pid" ]; then kill "$copy_pid" 2>/dev/null || true; wait "$copy_pid" 2>/dev/null || true; fi
  if [ -n "$copy_root" ]; then rm -rf "$copy_root"; fi
  if [ "$acquired" -eq 1 ]; then "$SLOT" release blackbox-audit; fi
  printf 'cleanup complete: owned servers stopped; heavy slot released\n' >> audit/lifecycle.log
}
trap cleanup EXIT INT TERM
"$SLOT" acquire blackbox-audit > audit/lifecycle.log
acquired=1
PORT=$(.venv/bin/python - <<'PY'
import socket
for p in (8730,8740):
 s=socket.socket()
 try: s.bind(('127.0.0.1',p))
 except OSError: s.close(); continue
 s.close(); print(p); break
else: raise SystemExit('Neither authorized port is available')
PY
)
COPY_PORT=$((PORT+1))
.venv/bin/python -m blackbox serve --port "$PORT" > audit/server.stdout.txt 2> audit/server.stderr.txt &
main_pid=$!
copy_root=$(mktemp -d /tmp/blackbox-audit-web.XXXXXX)
cp -R web "$copy_root/empty"
cp -R web "$copy_root/missing"
rm "$copy_root/empty/data/index.json"
rm "$copy_root/missing/data/slip_grip-000/run.json"
.venv/bin/python -m http.server "$COPY_PORT" --bind 127.0.0.1 --directory "$copy_root" > audit/copy-server.stdout.txt 2> audit/copy-server.stderr.txt &
copy_pid=$!
printf 'main PID=%s port=%s; copy PID=%s port=%s\n' "$main_pid" "$PORT" "$copy_pid" "$COPY_PORT" >> audit/lifecycle.log
.venv/bin/python - "$PORT" "$COPY_PORT" <<'PY'
import socket,sys,time
for port in map(int,sys.argv[1:]):
 for _ in range(50):
  try:
   with socket.create_connection(('127.0.0.1',port),timeout=.2): break
  except OSError: time.sleep(.1)
 else: raise SystemExit(f'Server {port} did not start')
PY
.venv/bin/python audit/scripts/run-cli.py > audit/cli/run.log 2>&1
NODE_PATH=/tmp/blackbox-audit-tools/node_modules node audit/scripts/run-browser.cjs "http://127.0.0.1:$PORT" "http://127.0.0.1:$COPY_PORT" > audit/browser/run.log 2>&1
