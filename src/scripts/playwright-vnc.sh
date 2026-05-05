#!/bin/bash
# Long-running command for the `playwright` docker-compose service.
# Boots Xvfb + a window manager + VNC, then idles waiting for `exec`.
# When the user runs `docker compose exec playwright ./test_ui ...` we want
# the virtual display already running so Chromium has somewhere to draw.
set -e

# Make sure Node deps + Chromium are installed. test_ui also runs this on
# every invocation so the container recovers if the cache disappears
# mid-life (e.g. someone wiped src/.ms-playwright while switching branches).
if [ ! -d node_modules/@playwright/test ]; then
  npm install --silent
fi
if ! npx playwright install chromium > /dev/null 2>&1; then
  # Verbose retry so a real failure (no network, disk full, etc.) is loud.
  npx playwright install chromium
fi

# Start the virtual display + VNC stack. Runs in the background; ports are
# exposed via docker-compose so http://localhost:7900 is your viewer.
Xvfb :99 -screen 0 1280x900x24 >/dev/null 2>&1 &
sleep 0.5
fluxbox -display :99 >/dev/null 2>&1 &
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -bg -quiet >/dev/null 2>&1
websockify --web=/usr/share/novnc/ 7900 localhost:5900 >/dev/null 2>&1 &

echo ""
echo "  Playwright VNC viewer:"
echo "    http://localhost:7900/vnc.html?autoconnect=1&resize=scale"
echo ""
echo "  Run tests with:"
echo "    docker compose exec playwright ./test_ui [--slow|--ui|--headed|--grep ...]"
echo ""

# Keep the container alive so `exec` works.
exec tail -f /dev/null
