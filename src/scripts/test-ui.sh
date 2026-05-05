#!/usr/bin/env bash
# Run the Playwright UI tests with the VNC viewer auto-opened in your
# browser. Single host command — same flags as `./test_ui` inside the
# container.
#
# Usage from src/:
#   ./scripts/test-ui.sh                          # headless
#   ./scripts/test-ui.sh --slow                   # watch in slow-mo
#   ./scripts/test-ui.sh --headed                 # watch normal speed
#   ./scripts/test-ui.sh --ui                     # Playwright UI
#   ./scripts/test-ui.sh --grep "Tab walks"       # filter
#
# What this does:
#   1. Brings the playwright service up (no-op if already running).
#   2. Waits for the VNC viewer port to respond.
#   3. Opens the viewer URL in your default browser.
#   4. Runs `docker compose exec playwright ./test_ui ...` with your flags.
set -euo pipefail
cd "$(dirname "$0")/.."

URL="http://localhost:7900/vnc.html?autoconnect=1&resize=scale"

# Whether we'll be drawing a browser. Skip the auto-open for headless runs.
visible=false
for arg in "$@"; do
    case "$arg" in --headed|--slow|--ui|--debug) visible=true ;; esac
done

# 1. Make sure the long-running playwright service is up.
docker compose up -d playwright >/dev/null

if $visible; then
    # 2. Wait for the noVNC port to respond before opening — otherwise the
    #    browser hits a connection-refused page.
    for _ in $(seq 1 60); do
        if curl -sf -o /dev/null "$URL" 2>/dev/null; then break; fi
        sleep 0.5
    done

    # 3. Open in your default browser.
    if command -v open >/dev/null 2>&1; then
        open "$URL"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1
    else
        echo "Open this in your browser: $URL"
    fi
fi

# 4. Run the tests inside the container.
exec docker compose exec playwright ./test_ui "$@"
